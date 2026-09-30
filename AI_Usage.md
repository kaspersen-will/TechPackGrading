# AI Usage Log

| Date/commit | Tool | Prompt | Disposition (Accepted/Modified/Rejected) | What changed & why (if modified) | In my own words, how this works |
|---|---|---|---|---|---|
| 27/09/26 / [commit hash] | Claude | Asked for a README placeholder before code | Modified | Setup and test sections left as placeholders because there is no code yet | No functionality/ code yet; also used to initialise this file |
| 28/09/26 / [commit hash] | Claude | App skeleton  | Accepted |  | App is built inside a function instead of import time so that tests can set data_dir to a temp folder, call create_app() and get a fresh app without touching the real data. Host set to 0.0.0.0 so that it accepts connections from any machine. Inside db.py get_connection() sets the foreign keys pragma on every connection so that grade rules don't start pointing to an ID that no longer exists. When initialising db, used a try/finally, and avoided using a with block as in sqlite that does not actually close the connection  |
| 29/09/26 / [commit hash] | Claude | Created test files for grading and the units | Accepted | | Testing whether the app catches out-of-tolerance samples correctly |
| 29/09/26 / [commit hash] | Claude | Created sql docstring for Schema | Modified | Fixed logic errors and had to adapt to changes made| |
| 30/09/26 / [commit hash] | Claude Code| Changed get_graded_spec to return style_code so domain 2 can snapshot it  | Modified | Had to fix the indexing and a add a few more assertions in the test | |
| 30/09/26 / [commit hash] | Claude Code| sqlite for get_style and delete_style | Accepted | | |
| 30/09/26 / [commit hash] | Claude | Created test_store_pages to test the three new functions for Domain 1's own pages directly against sqlite without flask. | Accepted | | |
| 30/09/26 / [commit hash] | Claude | Added placeholder html inside the templates for testing| Accepted | | |

