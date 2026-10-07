# spindle

A small Lisp in one file of dependency-free Python. `spindle.py` (~920 lines) is
the whole language: tokenizer, reader, evaluator, builtins, prelude, REPL.

## Commands

```sh
python3 test_spindle.py            # the test suite (also runs under pytest)
python3 spindle.py                 # REPL
python3 spindle.py examples/sorting.spin
for f in examples/*.spin; do python3 spindle.py "$f"; done   # smoke test
```

There is no build step, no virtualenv, and no config. Python 3.9+ (the source
uses `from __future__ import annotations`).

## Layout

`spindle.py` reads top to bottom as a pipeline, divided by `# ---- section`
banner comments: data types → tokenizer → reader → environment → procedures →
evaluator → printer → builtins → `PRELUDE` → main. Follow that order when
adding code; a new builtin goes next to its neighbours in `global_env()`, not
at the end.

`PRELUDE` at the bottom of `spindle.py` is the standard library **written in
spindle itself** and evaluated at startup. Prefer adding library functions
there over writing another Python builtin.

`examples/*.spin` are documentation that must keep running; they are the only
coverage some paths get outside the tests.

## Invariants

These are easy to break and the tests will not always catch it.

**Lisp values are plain Python values.** Lists are Python `list`s, so there are
no dotted pairs — `(a . b)` exists only in parameter lists. `Symbol` subclasses
`str`, so a Lisp string is *also* a `str`: distinguishing them always needs
`isinstance(x, Symbol)`. Use the `_text` / `_seq` / `_num` guards rather than
hand-rolling type checks.

**`bool` is a subclass of `int`.** Every numeric path must reject booleans
explicitly (`_num` does); `(+ 1 #t)` is an error, and there is a test for it.

**Only `#f` is false.** Never test a Lisp value with Python truthiness — use
`truthy(x)`. `0` and `'()` are both true. `NIL` is `[]`.

**Tail position must be preserved.** `evaluate` is a `while True` loop, not a
recursion: in tail position it reassigns `x` (and sometimes `env`) and
`continue`s. `if`, `cond`, `begin`, `let`, `let*`, `and`, `or`, macro
expansion, and `Lambda` application all do this, and `test_spindle.py` asserts
it for each. A new special form that evaluates a body **must** go through
`x = ...; continue` — calling `evaluate(...)` recursively silently costs
constant-space tail recursion. Non-tail recursion uses the Python stack, with
the limit raised to 20000 in `__main__` and in the test module.

**Errors are `LispError`, prefixed with the operator's name**, lowercase, no
trailing period: `raise LispError(f"nth: index {i} out of range ...")`. Tests
assert on substrings of these messages, so rewording one is a test change.
`LispError` is caught at the REPL and in `main`; nothing else should escape.

**No dependencies.** Standard library only — currently just `sys` and
`functools.reduce`. Keep it that way.

**Macros are unhygienic** by design. A template name can shadow one at the call
site (`swap!` in `examples/macros.spin` breaks on a variable named `held`).
Do not paper over it locally; it is documented in the README.

## Tests

`test_spindle.py` has no dependencies either. `main()` discovers every
module-level `test_*` function via `globals()` and runs it, so a new test just
needs that prefix. Write assertions through the three helpers at the top: `ev`
(evaluate in a fresh env), `shows` (evaluate, then `write` the result), and
`raises` (expect a `LispError`, return its message). Each test gets a fresh
`global_env()`, which re-parses `PRELUDE` — that is the cost of the suite and
it is fine.

Keep the suite green and keep the examples running before committing.

## Style

Lines stay under ~88 columns. Comments explain *why* (see the `eq?` and
`quotient` definitions), and docstrings are one or two sentences. Internal
Python helpers are `_`-prefixed; Lisp-visible names keep their Lisp spelling
(`string->number`, `null?`). Prose in the docs and comments is plain and
unhyped — match it.
