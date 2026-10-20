Assembly Stock Reconciliation v0.6.8 DIAGNOSTIC overlay

Purpose:
- Safely report the installed InvenTree Build.complete_allocations() signature.
- Does not modify stock or build data when the diagnostic URL is opened.
- Keeps the existing v0.6.7 commit behavior unchanged.

Extract over the ROOT of the existing GitHub repository.

Adds:
  assembly_stock_reconciliation/plugin_v068.py

Replaces:
  pyproject.toml

After updating the plugin through the InvenTree UI, while logged in, open:
  /plugin/assembly-stock-reconciliation/diagnostic/build-api/

Copy the JSON response back into ChatGPT.

Do not test Commit Reconciliation on production while diagnosing the old API.

Suggested commit message:
v0.6.8: add safe Build API compatibility diagnostic
