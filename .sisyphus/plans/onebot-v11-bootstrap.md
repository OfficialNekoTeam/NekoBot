# OneBot v11 Bootstrap Integration Plan

- [ ] Add platform bootstrap entrypoints so `NekoBotFramework` can load and start configured OneBot v11 instances.
- [ ] Define a first-pass application configuration shape for platform instances and bootstrap options.
- [ ] Integrate OneBot v11 transport startup into the real project entry path instead of leaving `main.py` as a framework self-check only.
- [ ] Add tests covering config-driven platform registration and startup flow.
- [ ] Verify full startup path with pytest, Ruff, basedpyright, and a bootstrap smoke check.
