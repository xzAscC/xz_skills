You are reviewing a pull request. The diff is attached. The repository is the current directory: read any file with the read, grep, find and ls tools. You cannot change files.

Find correctness problems that the change introduces: wrong results, crashes, broken edge cases, data loss, security holes, numbers in research code that change without a reason, and code that does not do what the change says it does. Before you report a problem, read the code around it and the callers of every changed function.

Do not report style, naming, formatting, missing comments or general advice.

For each finding give:

- `file:line` in the new version
- what is wrong, in one sentence
- a concrete scenario: input or state, then the wrong output or crash
- new in this diff, or pre-existing in unchanged code
- confidence: high, medium or low

End with the number of findings. If you find nothing, write "No issues found."
