# How-To Guide: Generating a Task List from a PRD

This guide helps AI assistants create a detailed, step-by-step task list based on an existing Product Requirements Document (PRDs).

The generated task list will follow the structure provided by the template `tasks-template.md`.

## Process

1. **Receive Initial Prompt with PRD Reference**:
   Receive the PRD and analyze it to understand the project / feature specifications.
2. **Assess Current State**:
   Review the existing codebase to understand existing infrastructure, architectural patterns, and conventions.
   Identify any existing components or features that already exist and could be relevant to the project / feature.
   Identify relevant files, components, and utilities that can be leveraged or need modification.
3. **Generate Parent Tasks**:
   Based on the PRD analysis and current state assessment, create the task list file and generate the main, high-level tasks required to implement the feature.
   Present these tasks to the developer in the specified format (so far without the sub-tasks).
   Wait for confirmation from the developer before generating sub-tasks.
4. **Generate Sub-Tasks**:
   Break down each parent task into smaller, actionable sub-tasks.
5. **Save Task List**:
   Save the generated markdown document as `[n]-tasks-[feature-name].md` inside the `specs/` directory, where `n` is a zero-padded 3-digit sequence starting from 001 (e.g., `specs/001-tasks-data-model.md`).

## Guidelines

### Target Audience

Assume the primary reader of the task list is a **junior developer** who will be implementing the feature with awareness of the existing codebase context.

### Tasks Structure

- Parent tasks should represent major implementation phases or components, while sub-tasks should be atomic, well defined, actionable and specific.
- Minimize the number of tasks and sub-tasks. If a straightforward implementation can be described by a single sub-task, do not artificially break it down into multiple sub-tasks.
- Do not explicitly create tasks or sub-tasks for writing tests - tests will be created for every item without having to mention it.

## Quality Validation

As the final step, validate you work by checking the following:

1. **Completeness**:
   Are all PRD requirements and specifications covered by the task list?
2. **Clarity**:
   Would a junior developer understand all the tasks?
3. **Logical flow**:
   Are the tasks and sub-tasks ordered logically and consistently?
