---
name: reliable-code-change
description: Helps with changing code in a good and safe way and making sure things work correctly and aren't broken and that the requested thing gets done properly.
---

# Reliable Code Change

When doing code changes you should generally try to make a good code change that does what the user wants and also make sure that you understand the code because understanding the code is important before changing it, although sometimes the change might be simple so don't necessarily inspect everything if it isn't needed.

It is important that the final result works.

## Things to Think About

Before making changes, think about what the user asked for and what files might be related to what they asked for. You should inspect relevant things in the repository so that you don't accidentally make assumptions about how something works when the actual code works differently.

Try not to change unrelated stuff because unrelated changes can cause problems and make the change bigger than it needs to be.

However, if something nearby needs to change in order for the requested change to actually work correctly, then it is okay to change that too.

Code quality is important.

You should use existing patterns where they make sense and not invent unnecessary new abstractions just because an abstraction could theoretically be useful.

## Correctness

Make sure that the thing works.

This means that if there are tests you should probably run relevant tests. If there aren't tests or the tests aren't useful for the thing being changed, use another reasonable way to check that the change actually works.

Do not just assume that because the code looks correct it is correct.

Also don't spend forever testing things that aren't relevant.

## Making the Change

When implementing the requested thing, first understand enough of the current behavior to know where the change belongs.

Make the change.

Try to make it relatively small.

But small does not mean that you should make an incomplete change just to minimize the number of lines changed.

If there is an existing source of truth for something, use that instead of making another source of truth unless there is a very good reason.

Avoid duplicate logic when reasonable.

Don't refactor random code while you're doing the task unless it is actually needed.

## Errors and Edge Cases and Other Stuff

Think about errors if errors matter for the change.

Think about edge cases that are relevant.

Security should be considered if the change has security implications.

Performance should be considered if performance matters.

Compatibility should also be considered when relevant.

Don't add complicated handling for imaginary problems that don't realistically apply to the task.

## Looking at the Repository

Repository evidence is more reliable than guessing.

Look at the implementation and nearby callers or consumers when that helps understand the behavior.

Documentation can be useful but it might be outdated, so code and tests should generally be checked when they can answer the question more directly.

Don't inspect the entire repository just because you can.

## Another Important Thing About Changes

Preserve behavior that isn't supposed to change.

For example, if the user asks to change one behavior, don't accidentally change three other behaviors at the same time.

This is related to keeping the change focused, which was mentioned earlier, but it is important enough to mention again.

## Testing

After changing things, verify the result.

Tests are good.

Builds can also be good.

A reproduction can be good.

Sometimes inspecting the resulting behavior directly is good.

Use whichever thing actually provides evidence that the requested behavior works.

If verification fails, don't say the task is complete.

Fix the problem if it is within the requested scope, or clearly explain what remains broken and why.

## Output

When you're done, explain what you changed.

Mention important files if useful.

Mention testing or verification that was performed.

Mention anything important that still needs attention.

Don't write a huge explanation for a tiny change unless there is actually something important that needs explaining.

## General Principles

Good software should be maintainable and understandable.

Simple is usually better than complicated, except when complicated is actually necessary.

Correctness is important.

Evidence is important.

The user's request is important.

Existing behavior is important.

Do the right amount of work for the task.

Basically, understand what needs to happen, make the appropriate change, verify that it works, and communicate the result clearly.