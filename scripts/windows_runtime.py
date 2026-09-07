"""Local Windows supervisor, verified snapshots and non-destructive recovery."""
import argparse
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime,timezone
from urllib.request import build_opener,ProxyHandler

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"runtime"
BACKUPS=ROOT/"backups"

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda:source.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def local_config(root=ROOT):
    # Same .env interpretation as backend; never print configuration or secrets.
    from dotenv import dotenv_values
    config=dotenv_values(root/".env")
    url=config.get("DATABASE_URL","sqlite:///./fusaa.db")
    if not url.startswith("sqlite:///"):raise RuntimeError("Local backup requires SQLite; use PostgreSQL backup tooling for production")
    database=Path(url.removeprefix("sqlite:///"))
    if not database.is_absolute():database=root/"backend"/database
    storage=Path(config.get("STORAGE_DIR","./storage"))
    if not storage.is_absolute():storage=root/"backend"/storage
    return database.resolve(),storage.resolve()

def check_snapshot(folder):
    folder=Path(folder).resolve()
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    for name,checksum in manifest["files"].items():
        target=(folder/name).resolve()
        if not target.is_relative_to(folder) or not target.is_file() or digest(target)!=checksum:
            raise RuntimeError("Backup verification failed: "+name)
    with sqlite3.connect((folder/"database.sqlite").as_uri()+"?mode=ro",uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise RuntimeError("SQLite snapshot is damaged")
        for (key,) in db.execute("SELECT storage_key FROM documents UNION SELECT preview_key FROM documents WHERE preview_key IS NOT NULL"):
            target=(folder/"storage"/key).resolve()
            if not target.is_relative_to(folder/"storage") or not target.is_file():raise RuntimeError("Backup document missing")
    return manifest

def backup(root=ROOT,destination=BACKUPS):
    root=Path(root).resolve();destination=Path(destination).resolve()
    database,storage=local_config(root)
    if not database.is_file():raise RuntimeError("Database unavailable")
    folder=destination/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    folder.mkdir(parents=True,exist_ok=False)
    with sqlite3.connect(database.as_uri()+"?mode=ro",uri=True) as source,sqlite3.connect(folder/"database.sqlite") as target:
        source.backup(target)
    shutil.copytree(storage,folder/"storage")
    for relative in ("backend/.env","local-agent/.env","local-agent/agent-state.json"):
        source=root/relative
        if source.exists():
            target=folder/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    manifest={"created_at":datetime.now(timezone.utc).isoformat(),"files":{str(p.relative_to(folder)).replace(os.sep,"/"):digest(p) for p in folder.rglob("*") if p.is_file()}}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    check_snapshot(folder)
    return folder

def restore(snapshot,destination):
    snapshot=Path(snapshot).resolve();destination=Path(destination).resolve()
    check_snapshot(snapshot)
    if destination.exists():raise RuntimeError("Recovery destination must be new; live data is never overwritten")
    shutil.copytree(snapshot,destination)
    check_snapshot(destination)
    return destination

def health(root=ROOT):
    opener=build_opener(ProxyHandler({}))
    checks={}
    for name,url in (("api","http://127.0.0.1:8000/readyz"),("ollama","http://127.0.0.1:11434/api/tags")):
        try:
            with opener.open(url,timeout=3) as response:data=json.load(response)
            checks[name]=data.get("status")=="ready" if name=="api" else bool(data.get("models"))
        except Exception:checks[name]=False
    try:
        database,_=local_config(root)
        with sqlite3.connect(database.as_uri()+"?mode=ro",uri=True) as db:
            row=db.execute("SELECT max(last_heartbeat_at) FROM computer_agents").fetchone()
            heartbeat=datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc) if row and row[0] else None
            checks["agent"]=bool(heartbeat and (datetime.now(timezone.utc)-heartbeat).total_seconds()<90)
    except Exception:checks["agent"]=False
    checks["last_check"]=datetime.now(timezone.utc).isoformat()
    return checks

def supervise():
    import msvcrt
    RUNTIME.mkdir(exist_ok=True)
    lock=(RUNTIME/"supervisor.lock").open("a+b");lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:return
    logger=logging.getLogger("fusaa.runtime");logger.setLevel(logging.INFO)
    handler=RotatingFileHandler(RUNTIME/"supervisor.log",maxBytes=2_000_000,backupCount=3,encoding="utf-8")
    logger.addHandler(handler)
    python=Path(sys.executable).with_name("python.exe")
    processes={};streams={};last_backup=None;last_backup_at=None;next_backup_try=0
    try:
        while True:
            checks=health()
            for name,folder,args in (("api",ROOT/"backend",["-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]),("agent",ROOT/"local-agent",["-m","fusaa_agent.main"])):
                child=processes.get(name)
                if child and child.poll() is None:continue
                # This supervisor owns both local services.  A fresh
                # supervisor must not trust a stale heartbeat and skip a
                # missing child; it starts the process and tracks its PID.
                if name in streams:streams[name].close()
                log_path=RUNTIME/(name+".log")
                if log_path.exists() and log_path.stat().st_size>5_000_000:
                    log_path.replace(RUNTIME/(name+".previous.log"))
                streams[name]=log_path.open("ab")
                processes[name]=subprocess.Popen([str(python),*args],cwd=folder,stdout=streams[name],stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                logger.info("Started %s pid=%s",name,processes[name].pid)
            if not checks["ollama"]:
                ollama=shutil.which("ollama")
                previous=processes.get("ollama")
                if ollama and (not previous or previous.poll() is not None):
                    processes["ollama"]=subprocess.Popen([ollama,"serve"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,env={**os.environ,"OLLAMA_HOST":"127.0.0.1:11434"})
            today=datetime.now(timezone.utc).date()
            if today!=last_backup and time.monotonic()>=next_backup_try:
                try:
                    folder=backup();last_backup=today;last_backup_at=datetime.now(timezone.utc).isoformat();logger.info("Verified backup %s",folder.name)
                except Exception:
                    logger.exception("Backup failed");next_backup_try=time.monotonic()+3600
            checks["backup_today"]=last_backup==today
            checks["backup_last_at"]=last_backup_at
            checks["pids"]={name:p.pid for name,p in processes.items() if p.poll() is None}
            temp=RUNTIME/"health.tmp";temp.write_text(json.dumps(checks,indent=2),encoding="utf-8");temp.replace(RUNTIME/"health.json")
            time.sleep(20)
    finally:
        for child in processes.values():
            if child.poll() is None:child.terminate()
        for stream in streams.values():stream.close()
        lock.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["supervise","health","backup","verify","restore"])
    parser.add_argument("--snapshot",type=Path)
    parser.add_argument("--destination",type=Path)
    args=parser.parse_args()
    if args.action=="supervise":supervise()
    elif args.action=="health":print(json.dumps(health(),indent=2))
    elif args.action=="backup":print(backup())
    elif args.action=="verify":check_snapshot(args.snapshot);print("Backup verified")
    elif args.action=="restore":print(restore(args.snapshot,args.destination))
