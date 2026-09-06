# Document processing and layout

`DocumentProcessor` never overwrites the uploaded document. Each rotate, resize, crop, fit-to-page or conversion writes a distinct `processed/print_ready_*.{png,pdf}` object and creates a new `Document` record linked in metadata to its source.

`LayoutEngine` is deterministic. Given source, paper, item dimensions, quantity, spacing and DPI, it calculates the grid from millimetres and 300 DPI (configurable 72–600). It refuses a quantity that does not fit rather than clipping it.

The current UI supports a rotation and a ready-to-print A4 card/photo/sticker sheet. API endpoints additionally support resize, crop, fit-to-page, conversion PDF, A3/A5 sheets and creation of a PrintJob from any derived file. The assistant may understand a layout request later, but it must route it to this engine and never calculate final positions itself.
