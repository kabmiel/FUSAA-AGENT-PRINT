# Print workflow

1. A signed-in user uploads PDF, JPEG or PNG and names an organization and workshop.
2. `PrintInspector` records pages/dimensions/DPI and creates the job in `WAITING_APPROVAL`.
3. The user selects a synchronized online printer and options; the job becomes `READY`.
4. Explicit confirmation creates one queued `AgentCommand` and audit record.
5. The outbound agent claims its command, downloads only the assigned document, and invokes its fixed Windows print path.
6. The agent reports the result; the API persists it and broadcasts the status over WebSocket.

The Local Agent uses Windows `printto` for the chosen printer, reports `PRINTING` after dispatch, and watches its spooler job when the driver exposes one. It reports completion only once that job has left the spooler. Drivers that do not expose a job identifier remain in `PRINTING`; the system never fabricates a completed print.
