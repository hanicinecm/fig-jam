# How-To Guide: Generating a Product Requirements Document (PRD)

This guide helps AI assistants create a detailed project or feature specification file in the form of a Product Requirements Document (PRD).

The PRD will be generated based on an initial prompt from the developer, the subsequent brainstorming session, and the `prd-template.md` template.

## Process

1. **Receive Initial Prompt**:
   The developer provides a brief description of the project being built, or a request for a new feature or functionality.
2. **Ask Clarifying Questions**:
   Before writing the PRD, the AI asks clarifying questions to gather the appropriate details.
3. **Generate the PRD**:
   Based on the initial prompt and the developer's answers to the clarifying questions, the assistant generates the PRD using the template as a scaffold.
4. **Save the PRD**:
   The PRD is saved as `[n]-prd-[feature-name].md` inside the `specs/` directory, where `n` is a zero-padded 3-digit sequence starting from 001 (e.g., `specs/001-prd-data-model.md`).
   The `specs/` directory will be created in the root folder if it does not exist.

Unless instructed otherwise, do *not* start implementing the PRD.

## Clarifying Questions

The assistant should adapt its questions based on the prompt, the nature of the feature, and the template.
The clarifying dialogue between the assistant and the developer must go into sufficient detail - assume the primary reader of the PRD is a **junior developer**.
The specifications should be explicit, unambiguous, and avoid jargon.

### Questions Guidelines

- Number questions so the developer can address multiple questions at once.
- Ask open-ended questions first to understand the scope and context, then follow up with specific questions to clarify technical details.
- Provide examples of what you need to know, and ask for examples if things are unclear.
- Do not make assumptions, but offer your best judgment.

## PRD Structure

The structure of the generated PRD will follow the provided template.

### Template Usage Notes

- The template structure does not need to be followed exactly; adapt the content to the specific feature. If a template section does not apply for the given feature, simply omit it.
- The generated PRD should be as thorough and complete as possible. Don't be afraid to add (ask for) various examples, code snippets, object signatures, schemas, complete public surface, full directory trees, etc.

## Quality Validation

As the final step, validate your work by checking the following:

1. **Completeness**:
   Are all the relevant template sections addressed?
2. **Clarity**:
   Would a junior developer understand this?
3. **Consistency**:
   Does the generated PRD not contradict itself?
4. **Scope**:
   Does the PRD match the intended scope?
5. **Improvements**:
   Is anything obvious missing from the PRD, which was not suggested by the template or initial prompt?
