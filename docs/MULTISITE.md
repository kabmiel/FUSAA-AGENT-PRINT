# Multi-site and central supervision

The hierarchy is Organization → Workshop → ComputerAgent → Printer. An organization `OWNER` or `ADMIN` can create workshops, assign workshop roles and view central supervision. Workshop roles are `MANAGER`, `OPERATOR` and `VIEWER`.

Jobs may be routed before printing to another workshop and optionally a printer belonging to that workshop. The route is audited; a job already printing or terminal cannot be moved.

`GET /api/v1/supervision?organization_id=...` returns an organization-level view of agents, printers and job counts grouped by workshop. Agents whose heartbeat is older than 90 seconds are marked offline by this supervision pass.
