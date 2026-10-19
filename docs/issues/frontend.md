# Frontend Issue Log

This document records frontend issues and expected behavior identified during testing. Requirements are being collected first; production code changes will follow after this round of issue collection is complete.

For entries involving a backend handoff, describe frontend behavior on the premise that the backend changes have already been completed, for example: “The backend now provides …; the frontend needs to …”. This wording states the handoff premise, not actual implementation progress. Track progress separately in each entry's status.

Backend issue BE-001 uses the existing archive error display and retry flow and does not require a new frontend issue.

## FE-001 Richer Chat Presentation and Rendering Categories

- Recorded: 2026-10-20
- Status: Implemented (Manuscript reading surface, three rendering categories, quotation recognition); awaiting testing.
- Scope: Visual presentation of chat content, rendering tag configuration, and output parsing.

### Overall Visual Direction

The chat presentation should feel richer, more beautiful, and more carefully crafted. Typography should be more pleasing to read, with text colors that harmonize with the current environment theme. Chat containers should have richer border details and artistic background treatments that create a cohesive reading atmosphere. Specific fonts, palettes, textures, and decorative treatments are left to frontend design.

Character dialogue needs additional visual emphasis so that speech is easy to distinguish from ordinary narration. Custom chain-of-thought content should appear in more refined collapsible containers, creating a clear yet harmonious hierarchy alongside the main prose.

### Three Rendering Categories

Output content has three rendering categories: chain of thought, main prose, and other content. Each category should have its own visual treatment. Main prose rendering includes the quotation treatments described below.

When users add a rendering tag, they must specify its rendering category. The category must affect how the content is displayed, rather than merely being stored as descriptive metadata. “Chain of thought” here refers to text contained within user-defined chain-of-thought tags.

### Two Types of Quotation Within Main Prose

- **Standalone quotation**: Character speech that occupies a paragraph of its own, such as `\n“角色说的话”\n`. It should receive a distinct treatment suited to the current environment theme and feel like a separate unit of dialogue. A chat bubble within the prose is one possible direction, not a mandatory design.
- **Inline quotation**: Character speech embedded within surrounding text, such as `其他内容，“角色说的话”，其他内容`. It only needs a theme-appropriate accent color to distinguish it from ordinary text while preserving continuous sentence reading.

Quotation delimiters are not limited to English quotation marks. They also include Chinese quotation marks and other bracket forms, such as square brackets. Recognition and presentation should account for these forms rather than support only the delimiter shown in the examples. The exact delimiter coverage, contextual interpretation, and parsing approach are left to subsequent frontend design.

### Implementation Direction and Design Freedom

This requirement may call for substantial changes to frontend output parsing and should not be treated solely as a local color or border adjustment. Preserve the content categories, quotation meanings, and reading hierarchy described above; the specific visual design, component structure, and parsing approach are left to frontend design. This entry does not assume additional backend changes.
