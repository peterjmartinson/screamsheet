Refactor screamsheet so it no longer sends print jobs directly. Instead, add a new config.yaml option to specify an output directory for generated PDF files. After generation, copy each PDF to this configured directory. Document the new output option in both config.yaml.example and the README. Make sure unit tests and shell scripts are updated accordingly. This change enables external tools (like dispatch) to handle delivery without further changes to screamsheet.

- Remove all direct calls to print_sheet/lp from code and scripts
- Add output.directory to config
- Ensure all generated PDFs are copied to the configured directory
- Update tests and documentation
- Explain in README how to sync this with your delivery system (e.g. dispatch)
