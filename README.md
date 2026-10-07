# sprout

A small Lisp, written from scratch in one file of dependency-free Python.

It started as an empty directory, so it had to grow its own everything: a
tokenizer, a reader, an evaluator that does not blow the stack on tail calls,
closures, macros, and a REPL. The standard library is written in sprout itself.

```
.
├── sprout.py        the language (~700 lines, no dependencies)
├── test_sprout.py   26 tests covering reader, evaluator, builtins, TCO
└── examples/
    ├── fizzbuzz.spr     the obligatory one
    ├── closures.spr     counters, objects, memoisation
    ├── sorting.spr      merge sort, and sorting records by a field
    ├── macros.spr       `while`, `swap!`, and threading macros
    └── mandelbrot.spr   the set, in ASCII, from recursion and floats
```

## Use it

```sh
python3 sprout.py                      # REPL
python3 sprout.py examples/sorting.spr  # run a file
python3 test_sprout.py                 # run the tests
```

```
$ python3 sprout.py
sprout - a small Lisp. (exit) or Ctrl-D to leave.
sprout> (define (fact n) (if (< n 2) 1 (* n (fact (- n 1)))))
fact
sprout> (fact 30)
265252859812191058636308480000000
sprout> (map (lambda (x) (* x x)) (range 1 6))
(1 4 9 16 25)
```

The REPL keeps reading while a form is unfinished, so you can paste or type
multi-line definitions without escaping anything.

## The language in one page

**Atoms.** Integers and floats (`42`, `-3.5`), strings (`"hi\n"`), booleans
(`#t`, `#f`), symbols (`foo`, `string->number`), and the empty list `'()`.
Integers are Python's, so they never overflow.

**Truth.** Only `#f` is false. `0` and `'()` are both true, as in Scheme.

**Special forms.**

```lisp
(quote x)   'x                  ; or the reader shorthand
(if test then else)             ; else is optional
(define x 10)
(define (f a b) body ...)       ; sugar for (define f (lambda (a b) ...))
(set! x 11)
(lambda (a b) body ...)
(lambda (a . rest) ...)         ; rest takes the remaining arguments as a list
(lambda args ...)               ; all arguments as one list
(begin a b c)                   ; value of the last form
(let  ((a 1) (b 2)) ...)        ; bindings evaluated in the outer scope
(let* ((a 1) (b (+ a 1))) ...)  ; each binding sees the previous ones
(cond (test body ...) ... (else body ...))
(and a b)  (or a b)             ; short-circuiting, return the deciding value
(defmacro name (params) body)
`(a ,b ,@cs)                    ; quasiquote, unquote, unquote-splicing
```

**Builtins.** Arithmetic (`+ - * / quotient modulo remainder abs min max sqrt
expt`), comparison (`= < > <= >= not eq? equal?`), lists (`cons car cdr list
append length reverse nth range apply map filter fold`), strings
(`string-append string-length string-ref substring string=? string<? string>?
string->number number->string symbol->string string->symbol`), predicates
(`null? pair? list? number? integer? string? symbol? boolean? procedure? even?
odd? zero?`), and `display`, `newline`, `print`, `write`, `error`, `assert`.

**Prelude**, written in sprout at the bottom of `sprout.py`: `caar cadr cddr
caddr when unless inc! identity 1+ 1- for-each last take drop sum product
member assoc any? all? sort string-join compose`.

## Two things worth a closer look

**Tail calls don't grow the stack.** `evaluate` is a loop, not a recursion.
When a call sits in tail position the loop rebinds `x` and `env` and goes
round again instead of calling itself, so a tail-recursive loop runs in
constant space. `if`, `cond`, `begin`, `let`, `and`, `or`, macro expansion,
and procedure application all preserve tail position:

```lisp
(define (count-to n acc) (if (= n 0) acc (count-to (- n 1) (+ acc 1))))
(count-to 1000000 0)            ; fine
```

Non-tail recursion still uses the Python stack, which is raised to 20000
frames.

**Macros are plain functions over code.** `defmacro` makes a procedure whose
arguments arrive unevaluated and whose return value is spliced back in as
source. Quasiquote makes the templates readable, and the expansion happens in
tail position, so a recursive macro like `->` costs nothing at runtime:

```lisp
(defmacro while (test . body)
  `(let ((spin '()))
     (set! spin (lambda () (when ,test ,@body (spin))))
     (spin)))
```

Macros are unhygienic — a name introduced by a template can shadow one at the
call site. That is a real limitation, not a subtlety: `swap!` in
`examples/macros.spr` breaks if you pass it a variable named `held`.

## Deliberately missing

Dotted pairs (lists are Python lists, so `(a . b)` exists only in parameter
lists), proper rationals, `call/cc`, hygienic macros, a module system, and any
attempt at speed.
