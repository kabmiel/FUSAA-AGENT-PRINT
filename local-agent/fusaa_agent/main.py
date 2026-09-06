import hashlib
import asyncio
import json
import logging
import os
import platform
import time
import threading
from pathlib import Path
from .printing import render_job
from .desktop_watcher import DesktopWatcher
import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("fusaa-agent")
PROJECT_DIR=Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=PROJECT_DIR/".env",extra="ignore")
    backend_url:str="http://localhost:8000"
    enrollment_token:str=""
    state_file:Path=Path("agent-state.json")
    poll_seconds:int=5
    max_backoff_seconds:int=60
    desktop_watch_enabled:bool=True
    desktop_watch_directory:Path=Field(default_factory=lambda:Path.home()/"Desktop")
    desktop_watch_state_file:Path=Path("desktop-watch-state.json")
    desktop_watch_health_file:Path=Path("desktop-watch-health.json")
    desktop_watch_poll_seconds:float=2
    desktop_watch_stable_seconds:float=4

class Agent:
    def __init__(self,settings:Settings):
        self.s=settings;self.client=httpx.Client(base_url=settings.backend_url.rstrip("/"),timeout=30);self.state=self._load_state();self.wakeup=threading.Event()
        self.desktop_stop=threading.Event();self.desktop_watcher=None
    def _load_state(self):
        if self.s.state_file.exists():return json.loads(self.s.state_file.read_text())
        return {}
    def _save_state(self):
        temporary=self.s.state_file.with_suffix(".tmp")
        with temporary.open("w",encoding="utf-8") as stream:
            json.dump(self.state,stream);stream.flush();os.fsync(stream.fileno())
        temporary.replace(self.s.state_file)
    def fingerprint(self):return hashlib.sha256(f"{platform.node()}|{platform.system()}|{os.getenv('COMPUTERNAME','')}".encode()).hexdigest()
    @property
    def headers(self):return {"X-Agent-Key":self.state["agent_key"]}
    def enroll(self):
        if self.state:return
        if not self.s.enrollment_token:raise RuntimeError("ENROLLMENT_TOKEN is required for first start")
        r=self.client.post("/api/v1/agent/register",json={"enrollment_token":self.s.enrollment_token,"machine_fingerprint":self.fingerprint()});r.raise_for_status();self.state=r.json();self._save_state();log.info("Enrolled agent %s",self.state["agent_id"])
    def printers(self):
        try:
            import win32print
        except ImportError:
            log.warning("pywin32 unavailable: printer discovery is disabled")
            return []
        result=[]
        for _,_,name,_ in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL|win32print.PRINTER_ENUM_CONNECTIONS):
            result.append({"system_name":name,"name":name,"status":self.printer_status(win32print,name),"capabilities":{"discovered_by":"win32print"}})
        return result
    def printer_status(self,win32print,printer):
        try:
            handle=win32print.OpenPrinter(printer)
            try: flags=win32print.GetPrinter(handle,2).get("Status",0)
            finally: win32print.ClosePrinter(handle)
        except Exception as error: log.warning("Cannot query printer %s: %s",printer,error);return "UNKNOWN"
        checks=[("OFFLINE",getattr(win32print,"PRINTER_STATUS_OFFLINE",0x80)),("PAPER_OUT",getattr(win32print,"PRINTER_STATUS_PAPER_OUT",0x10)),("PAPER_JAM",getattr(win32print,"PRINTER_STATUS_PAPER_JAM",0x08)),("ERROR",getattr(win32print,"PRINTER_STATUS_ERROR",0x02)),("PRINTING",getattr(win32print,"PRINTER_STATUS_PRINTING",0x400)),("BUSY",getattr(win32print,"PRINTER_STATUS_BUSY",0x200))]
        return next((name for name,flag in checks if flags & flag),"ONLINE")
    def sync(self):
        self.client.post(f"/api/v1/agent/{self.state['agent_id']}/heartbeat",headers=self.headers,json={}).raise_for_status()
        r=self.client.put(f"/api/v1/agent/{self.state['agent_id']}/printers",headers=self.headers,json=self.printers());r.raise_for_status()
    def report_desktop_event(self,event):
        response=self.client.post(f"/api/v1/agent/{self.state['agent_id']}/desktop-events",headers=self.headers,json=event)
        response.raise_for_status()
    def start_desktop_watcher(self):
        if not self.s.desktop_watch_enabled:
            log.info("Desktop watcher disabled by configuration")
            return
        try:
            self.desktop_watcher=DesktopWatcher(
                self.s.desktop_watch_directory,
                self.s.desktop_watch_state_file,
                self.s.desktop_watch_health_file,
                stable_seconds=self.s.desktop_watch_stable_seconds,
                poll_seconds=self.s.desktop_watch_poll_seconds,
                max_backoff_seconds=self.s.max_backoff_seconds,
                agent_id=self.state["agent_id"],
            )
            self.desktop_watcher.set_agent_id(self.state["agent_id"])
        except Exception:
            self.desktop_watcher=None
            log.exception("Desktop watcher unavailable; continuing without it")
            return
        threading.Thread(
            target=self.desktop_watcher.run,
            args=(self.report_desktop_event,self.desktop_stop),
            name="fusaa-desktop-watch",
            daemon=True,
        ).start()
        log.info("Watching Desktop folder %s",self.s.desktop_watch_directory)
    def execute(self,cmd):
        # The agent never receives shell commands. This fixed handler is the only physical-action boundary.
        if cmd["type"]=="CANCEL": return self.cancel(cmd)
        if cmd["type"]!="PRINT":raise RuntimeError("Unsupported command")
        doc_id=cmd["payload"].get("document_id")
        printer=cmd["payload"].get("printer_system_name")
        if not doc_id or not printer:raise RuntimeError("Command lacks a document or printer")
        import uuid
        command_id=str(uuid.UUID(cmd["id"]));document_id=str(uuid.UUID(doc_id))
        response=self.client.get(f"/api/v1/agent/{self.state['agent_id']}/documents/{document_id}",headers=self.headers)
        response.raise_for_status()
        extension={"application/pdf":".pdf","image/png":".png","image/jpeg":".jpg"}.get(response.headers.get("content-type","").split(";")[0])
        if not extension:raise RuntimeError("Unsupported document type")
        target=Path("spool")/f"{command_id}-{document_id}{extension}";target.parent.mkdir(exist_ok=True)
        target.write_bytes(response.content)
        return render_job(target,printer,cmd["payload"],"FUSAA "+command_id)
    def spooler_job_ids(self,win32print,printer):
        try:
            handle=win32print.OpenPrinter(printer)
            try: return {job["JobId"] for job in win32print.EnumJobs(handle,0,999,1)}
            finally: win32print.ClosePrinter(handle)
        except Exception as error:
            log.warning("Cannot query spooler for %s: %s",printer,error);return set()
    def cancel(self,cmd):
        payload=cmd["payload"];printer=payload.get("printer_system_name");job_id=payload.get("spooler_job_id")
        if not printer or job_id is None: raise RuntimeError("Cancellation unavailable: no spooler job is being tracked")
        try: import win32print
        except ImportError: raise RuntimeError("Cancellation unavailable: install pywin32")
        handle=win32print.OpenPrinter(printer)
        try: win32print.SetJob(handle,int(job_id),0,None,win32print.JOB_CONTROL_CANCEL)
        finally: win32print.ClosePrinter(handle)
        return {"printer":printer,"spooler_job_id":job_id,"cancelled_by_windows":True}
    def queue(self): return self.state.setdefault("queue",{})
    def receive_commands(self):
        r=self.client.get(f"/api/v1/agent/{self.state['agent_id']}/commands",headers=self.headers);r.raise_for_status()
        for command in r.json(): self.queue().setdefault(command["id"],{"command":command,"executed":False,"report":None})
        self._save_state()
    def process_queue(self):
        for command_id,entry in list(self.queue().items()):
            if entry.get("acknowledged"):continue
            command=entry["command"]
            if entry.get("dispatch_started") and not entry["executed"]:
                entry["executed"]=True
                entry["report"]={"status":"FAILED","error_message":"Dispatch interrupted: outcome unknown. Check the printer before creating a new job."}
                self._save_state()
            if not entry["executed"]:
                # Durable intent before any physical side effect: never replay an uncertain dispatch.
                entry["dispatch_started"]=True;self._save_state()
                try: entry["report"]={"status":"SUCCESS" if command["type"]=="CANCEL" else "DISPATCHED","result":self.execute(command)}
                except Exception as error: log.exception("Command failed");entry["report"]={"status":"FAILED","error_message":str(error)}
                entry["executed"]=True;self._save_state()
            try:
                self.client.post(f"/api/v1/agent/{self.state['agent_id']}/commands/{command_id}/result",headers=self.headers,json=entry["report"]).raise_for_status()
                if entry["report"]["status"]=="FAILED": entry["acknowledged"]=True
                elif entry["report"]["status"]=="DISPATCHED":
                    job_id=entry["report"]["result"].get("spooler_job_id")
                    printer=entry["report"]["result"]["printer"]
                    # No job id means the printer driver cannot be reliably tracked: do not fabricate completion.
                    if job_id is not None:
                        import win32print
                        handle=win32print.OpenPrinter(printer)
                        try:
                            try:info=win32print.GetJob(handle,int(job_id),1)
                            except Exception as error:
                                # Normal spooler exit: the print subsystem finished sending data to the printer.
                                if getattr(error,"winerror",None) not in {87,2}:raise
                                entry["report"]={"status":"SUCCESS","result":{**entry["report"]["result"],"spooler_state":"COMPLETED"}}
                            else:
                                flags=info.get("Status",0)
                                if flags & (getattr(win32print,"JOB_STATUS_PRINTED",128)|getattr(win32print,"JOB_STATUS_COMPLETE",4096)):
                                    entry["report"]={"status":"SUCCESS","result":{**entry["report"]["result"],"spooler_state":"COMPLETED"}}
                                elif flags & (getattr(win32print,"JOB_STATUS_DELETED",256)|getattr(win32print,"JOB_STATUS_ERROR",2)):
                                    entry["report"]={"status":"FAILED","error_message":"Windows reports a deleted or failed print job"}
                        finally:win32print.ClosePrinter(handle)
                else: entry["acknowledged"]=True
                self._save_state()
            except httpx.HTTPError: log.warning("Result for %s retained locally for retry",command_id)
    def start_command_socket(self):
        def worker():
            async def listen():
                import websockets
                url=self.s.backend_url.rstrip("/").replace("https://","wss://").replace("http://","ws://")+f"/ws/agent/{self.state['agent_id']}?key={self.state['agent_key']}"
                delay=2
                while True:
                    try:
                        async with websockets.connect(url,ping_interval=20,ping_timeout=20) as ws:
                            delay=2;await ws.send("READY")
                            async for _ in ws:self.wakeup.set()
                    except Exception as error:
                        log.warning("Agent WSS disconnected: %s",error);await asyncio.sleep(delay);delay=min(delay*2,self.s.max_backoff_seconds)
            asyncio.run(listen())
        threading.Thread(target=worker,name="fusaa-wss",daemon=True).start()
    def run(self):
        # Windows file lock survives crashes safely and prevents two active agents.
        import msvcrt
        self._instance_lock=open(self.s.state_file.with_suffix(".lock"),"a+b")
        self._instance_lock.seek(0)
        try:msvcrt.locking(self._instance_lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError("Another FUSAA agent already uses this state file")
        self.enroll()
        self.start_desktop_watcher()
        self.start_command_socket()
        delay=self.s.poll_seconds
        while True:
            try:
                self.sync();self.receive_commands();self.process_queue();delay=self.s.poll_seconds
            except Exception: log.exception("Agent cycle failed; retrying in %ss",delay);delay=min(delay*2,self.s.max_backoff_seconds)
            self.wakeup.wait(delay);self.wakeup.clear()

if __name__=="__main__":Agent(Settings()).run()
