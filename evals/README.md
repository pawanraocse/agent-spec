# evals

`golden-tickets.csv` holds tickets the team already root-caused by hand (header only until filled).
`baseline.txt` holds the BugBot baseline as `<strict%>/<directional%>`, set from the AUTO-3807 run.
Run `/agent-spec-hub-runner eval` (skill `agent-spec-wf-eval`) after each key has a finished
`agent-spec-wf-rca` run. No customer data in this folder.
