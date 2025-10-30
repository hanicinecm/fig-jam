# How-To Guide: Implementing Tasks

This document provides guidelines for AI assistants to implement tasks listed in a task list markdown file.

## Feature Branch Check

Feature development should happen on a feature branch with a name that is consistent with the feature name.
If you are asked to start implementing tasks from an untouched task list, check the current branch and alert the user if its name is not consistent with the feature being implemented.

## Task Implementation Guidelines

- **One sub-task at a time**:
  Do not start the next sub-task until you receive confirmation from the developer.
  Mark the task as complete with `[x]` only after confirmation from the developer.
- **Test as you go**:
  Run relevant tests after implementing each sub-task to identify issues early.
- **Report changes**:
  Briefly explain what was implemented and any important decisions made.
- **Maintain consistency**:
  Add or modify tasks as they are identified and keep the `Relevant Files` section in the task list up to date.
- **Commit changes**:
  Once all sub-tasks for a parent task are complete (and confirmed by the developer), offer to finalize the parent task (see the *Parent Task Finalization* section below).
- **Handle blockers**:
  If a sub-task is blocked by missing information or dependencies, clearly communicate the issue to the developer, ask for clarification, or suggest a solution.
  Always ask questions before making assumptions.
- **Handle scope changes**:
  If the implementation shows that the task scope needs to be adjusted, propose specific changes to the task list and get approval before proceeding.
- **Technical challenges**:
  If an alternative approach is needed, explain the trade-offs and get the developer's input before deviating from the planned approach.

## Parent Task Finalization

The following is the process for finalizing a parent task, after all of its sub-tasks are marked as complete and the developer gives the go-ahead.

1. Lint and format the entire project.
2. Run the full test suite, if applicable.
3. Clean up all temporary files and code.
4. Mark the parent task as complete.
5. Unless instructed otherwise, stage all the changes and commit them using the conventional commit format. The commit message should reference the task number.

## Task List Finalization

Once the tasks from the current task list have been completed, offer to finalize the feature.

Feature finalization consists of squashing all the commits and merging into the `dev` branch.
Follow the specified commit format and reference the feature name in the commit message.
Instead of doing this autonomously, present the intent in detail to the developer and ask for the go-ahead.
