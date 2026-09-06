# Business foundation

Phase 8 introduces customers, products, services, deterministic price rules, print-cost estimates, invoices and payment records.

Price rules are evaluated by ascending priority and only against explicit conditions: paper size, color mode, printer, and copy ranges. The pricing formula is `base + per_copy × copies + per_page × pages × copies`. If no rule matches, the estimate is zero and clearly records that no rule was selected; the system never invents a price.

Invoices are lightweight drafts created from PrintJobs and their estimated/final costs. Payments update an invoice to `PARTIALLY_PAID` or `PAID`. They are an operational ledger, not a replacement for statutory accounting software.
