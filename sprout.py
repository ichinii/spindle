#!/usr/bin/env python3
"""sprout - a small Lisp that grew out of an empty folder.

Dependency-free: a tokenizer, a reader, a tail-call-optimised evaluator,
macros, closures, and a REPL. Run `python3 sprout.py` for the REPL or
`python3 sprout.py file.spr` to execute a file.
"""

from __future__ import annotations

import sys
from functools import reduce


# ---------------------------------------------------------------- data types

class Symbol(str):
    """An identifier. Subclasses str so it is hashable and cheap, but stays
    distinguishable from Lisp string values (which are plain str)."""
    __slots__ = ()


class LispError(Exception):
    pass


NIL: list = []          # the empty list, also Lisp's "nothing"
QUOTE = Symbol("quote")
QUASI = Symbol("quasiquote")
UNQUOTE = Symbol("unquote")
SPLICE = Symbol("unquote-splicing")
DOT = Symbol(".")
ELSE = Symbol("else")


def truthy(x) -> bool:
    """Scheme-flavoured truth: only #f is false. 0 and '() are true."""
    return x is not False


# ------------------------------------------------------------------ tokenizer

class Token:
    __slots__ = ("kind", "text", "line")

    def __init__(self, kind: str, text: str, line: int):
        self.kind = kind    # '(' ')' 'quote' 'quasi' 'unquote' 'splice' 'str' 'atom'
        self.text = text
        self.line = line

    def __repr__(self):
        return f"<{self.kind}:{self.text!r}@{self.line}>"


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"'}
_DELIMS = "()\";'`,"
_PREFIX = {"'": "quote", "`": "quasi"}


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    i, n, line = 0, len(src), 1
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == ";":                                   # comment to end of line
            while i < n and src[i] != "\n":
                i += 1
        elif c in "()":
            tokens.append(Token(c, c, line))
            i += 1
        elif c in _PREFIX:
            tokens.append(Token(_PREFIX[c], c, line))
            i += 1
        elif c == ",":
            if src[i + 1:i + 2] == "@":
                tokens.append(Token("splice", ",@", line))
                i += 2
            else:
                tokens.append(Token("unquote", ",", line))
                i += 1
        elif c == '"':
            buf, j = [], i + 1
            while True:
                if j >= n:
                    raise LispError(f"line {line}: unterminated string")
                d = src[j]
                if d == "\\":
                    nxt = src[j + 1:j + 2]
                    if not nxt:
                        raise LispError(f"line {line}: dangling escape in string")
                    buf.append(_ESCAPES.get(nxt, nxt))
                    j += 2
                elif d == '"':
                    j += 1
                    break
                else:
                    if d == "\n":
                        line += 1
                    buf.append(d)
                    j += 1
            tokens.append(Token("str", "".join(buf), line))
            i = j
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in _DELIMS:
                j += 1
            tokens.append(Token("atom", src[i:j], line))
            i = j
    return tokens


# --------------------------------------------------------------------- reader

def atom(text: str):
    if text == "#t":
        return True
    if text == "#f":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return Symbol(text)


def _read(tokens: list[Token], pos: int):
    if pos >= len(tokens):
        raise LispError("unexpected end of input")
    tok = tokens[pos]
    if tok.kind == "(":
        items, pos = [], pos + 1
        while True:
            if pos >= len(tokens):
                raise LispError(f"line {tok.line}: unclosed '('")
            if tokens[pos].kind == ")":
                return items, pos + 1
            item, pos = _read(tokens, pos)
            items.append(item)
    if tok.kind == ")":
        raise LispError(f"line {tok.line}: unexpected ')'")
    if tok.kind == "str":
        return tok.text, pos + 1
    if tok.kind == "atom":
        return atom(tok.text), pos + 1
    wrapper = {"quote": QUOTE, "quasi": QUASI,
               "unquote": UNQUOTE, "splice": SPLICE}[tok.kind]
    inner, pos = _read(tokens, pos + 1)
    return [wrapper, inner], pos


def parse(src: str) -> list:
    """Read every top-level form in `src`."""
    tokens, forms, pos = tokenize(src), [], 0
    while pos < len(tokens):
        form, pos = _read(tokens, pos)
        forms.append(form)
    return forms


def complete(src: str) -> bool:
    """True when `src` has no unclosed form - used by the REPL to keep reading."""
    try:
        depth = 0
        for tok in tokenize(src):
            if tok.kind == "(":
                depth += 1
            elif tok.kind == ")":
                depth -= 1
                if depth < 0:
                    return True          # error, but let the reader report it
        return depth == 0
    except LispError:
        return False


# ---------------------------------------------------------------- environment

class Env:
    __slots__ = ("vars", "parent")

    def __init__(self, vars=None, parent=None):
        self.vars = dict(vars or {})
        self.parent = parent

    def lookup(self, name: Symbol):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise LispError(f"unbound symbol: {name}")

    def set(self, name: Symbol, value):
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        raise LispError(f"set!: {name} is not defined")

    def define(self, name: Symbol, value):
        self.vars[name] = value


# ------------------------------------------------------------------ procedures

class Lambda:
    """A closure: parameters, a body, and the environment it was born in."""

    __slots__ = ("params", "rest", "body", "env", "name")

    def __init__(self, params, body, env, name="lambda"):
        self.rest = None
        if isinstance(params, Symbol):           # (lambda args ...) - collect all
            self.params, self.rest = [], params
        else:
            if len(params) >= 2 and params[-2] == DOT:
                self.rest = params[-1]
                params = params[:-2]
            if any(p == DOT for p in params):
                raise LispError("misplaced '.' in parameter list")
            for p in params:
                if not isinstance(p, Symbol):
                    raise LispError(f"bad parameter: {write(p)}")
            self.params = list(params)
        self.body = [Symbol("begin")] + list(body)
        self.env = env
        self.name = name

    def bind(self, args) -> Env:
        need, got = len(self.params), len(args)
        if got < need or (self.rest is None and got > need):
            expected = f"{need}+" if self.rest else str(need)
            raise LispError(f"{self.name}: expected {expected} args, got {got}")
        frame = dict(zip(self.params, args))
        if self.rest is not None:
            frame[self.rest] = list(args[need:])
        return Env(frame, self.env)

    def __call__(self, *args):
        return evaluate(self.body, self.bind(args))

    def __repr__(self):
        return f"#<procedure {self.name}>"


class Macro:
    """Like a Lambda, but receives its arguments unevaluated and returns code."""

    __slots__ = ("transformer",)

    def __init__(self, transformer: Lambda):
        self.transformer = transformer

    def expand(self, args):
        return evaluate(self.transformer.body, self.transformer.bind(args))

    def __repr__(self):
        return f"#<macro {self.transformer.name}>"


def call(proc, args):
    """Apply `proc` to a list of already-evaluated arguments."""
    if isinstance(proc, Lambda):
        return evaluate(proc.body, proc.bind(args))
    if callable(proc):
        return proc(*args)
    raise LispError(f"not a procedure: {write(proc)}")


# ------------------------------------------------------------------ evaluator

def _quasi(form, env, depth=1):
    """Expand a quasiquoted template, honouring nesting."""
    if not isinstance(form, list) or not form:
        return form
    head = form[0]
    if head == UNQUOTE and len(form) == 2:
        if depth == 1:
            return evaluate(form[1], env)
        return [UNQUOTE, _quasi(form[1], env, depth - 1)]
    if head == QUASI and len(form) == 2:
        return [QUASI, _quasi(form[1], env, depth + 1)]
    out = []
    for item in form:
        if isinstance(item, list) and len(item) == 2 and item[0] == SPLICE:
            spliced = evaluate(item[1], env) if depth == 1 else None
            if depth == 1:
                if not isinstance(spliced, list):
                    raise LispError("unquote-splicing: expected a list")
                out.extend(spliced)
            else:
                out.append([SPLICE, _quasi(item[1], env, depth - 1)])
        else:
            out.append(_quasi(item, env, depth))
    return out


def evaluate(x, env: Env):
    """Evaluate one form. Loops instead of recursing in tail position, so
    tail-recursive Lisp functions run in constant Python stack space."""
    while True:
        if isinstance(x, Symbol):
            return env.lookup(x)
        if not isinstance(x, list):
            return x                                   # numbers, strings, bools
        if not x:
            return NIL

        op = x[0]

        if isinstance(op, Symbol):
            if op == QUOTE:
                _arity(x, 2, "quote")
                return x[1]

            if op == "if":
                if len(x) not in (3, 4):
                    raise LispError("if: expected (if test then [else])")
                if truthy(evaluate(x[1], env)):
                    x = x[2]
                elif len(x) == 4:
                    x = x[3]
                else:
                    return NIL
                continue

            if op == "define":
                if len(x) < 3:
                    raise LispError("define: expected (define name value)")
                target = x[1]
                if isinstance(target, list):           # (define (f a) body...)
                    if not target or not isinstance(target[0], Symbol):
                        raise LispError("define: bad function header")
                    name = target[0]
                    value = Lambda(target[1:], x[2:], env, name)
                else:
                    _arity(x, 3, "define")
                    name = target
                    value = evaluate(x[2], env)
                    if isinstance(value, Lambda) and value.name == "lambda":
                        value.name = name
                env.define(name, value)
                return Symbol(name)

            if op == "set!":
                _arity(x, 3, "set!")
                env.set(x[1], evaluate(x[2], env))
                return NIL

            if op == "lambda":
                if len(x) < 3:
                    raise LispError("lambda: expected (lambda params body...)")
                return Lambda(x[1], x[2:], env)

            if op == "defmacro":
                if len(x) < 4:
                    raise LispError("defmacro: expected (defmacro name params body...)")
                env.define(x[1], Macro(Lambda(x[2], x[3:], env, x[1])))
                return Symbol(x[1])

            if op == QUASI:
                _arity(x, 2, "quasiquote")
                return _quasi(x[1], env)

            if op == "begin":
                if len(x) == 1:
                    return NIL
                for form in x[1:-1]:
                    evaluate(form, env)
                x = x[-1]
                continue

            if op in ("let", "let*"):
                if len(x) < 3 or not isinstance(x[1], list):
                    raise LispError(f"{op}: expected ({op} ((name value)...) body...)")
                inner = Env(parent=env)
                for binding in x[1]:
                    if not (isinstance(binding, list) and len(binding) == 2):
                        raise LispError(f"{op}: bad binding {write(binding)}")
                    source = inner if op == "let*" else env
                    inner.define(binding[0], evaluate(binding[1], source))
                env = inner
                x = [Symbol("begin")] + x[2:]
                continue

            if op == "cond":
                for clause in x[1:]:
                    if not isinstance(clause, list) or not clause:
                        raise LispError("cond: bad clause")
                    if clause[0] == ELSE or truthy(evaluate(clause[0], env)):
                        x = [Symbol("begin")] + clause[1:] if len(clause) > 1 \
                            else clause[0]
                        break
                else:
                    return NIL
                continue

            if op in ("and", "or"):
                want = op == "and"
                if len(x) == 1:
                    return want
                for form in x[1:-1]:
                    value = evaluate(form, env)
                    if truthy(value) is not want:
                        return value
                x = x[-1]
                continue

            # macro use: expand, then evaluate the expansion in tail position
            try:
                head = env.lookup(op)
            except LispError:
                head = None
            if isinstance(head, Macro):
                x = head.expand(x[1:])
                continue

        proc = evaluate(op, env)
        args = [evaluate(a, env) for a in x[1:]]
        if isinstance(proc, Lambda):
            env = proc.bind(args)
            x = proc.body
            continue
        if isinstance(proc, Macro):
            raise LispError(f"macro {op} used as a value")
        if not callable(proc):
            raise LispError(f"not a procedure: {write(proc)}")
        return proc(*args)


def _arity(form, n, name):
    if len(form) != n:
        raise LispError(f"{name}: expected {n - 1} argument(s), got {len(form) - 1}")


# -------------------------------------------------------------------- printer

def write(x) -> str:
    """Render a value the way the reader would accept it back."""
    if x is True:
        return "#t"
    if x is False:
        return "#f"
    if isinstance(x, Symbol):
        return str(x)
    if isinstance(x, str):
        body = (x.replace("\\", "\\\\").replace('"', '\\"')
                 .replace("\n", "\\n").replace("\t", "\\t"))
        return f'"{body}"'
    if isinstance(x, list):
        return "(" + " ".join(write(i) for i in x) + ")"
    if isinstance(x, float) and x.is_integer():
        return f"{x:.1f}"
    if x is None:
        return "()"
    return str(x)


def display(x) -> str:
    """Render a value for humans: strings without their quotes."""
    if isinstance(x, str) and not isinstance(x, Symbol):
        return x
    return write(x)


# ------------------------------------------------------------------- builtins

def _num(name, x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise LispError(f"{name}: expected a number, got {write(x)}")
    return x


def _fold_num(name, fn, args, unit=None):
    nums = [_num(name, a) for a in args]
    if not nums:
        if unit is None:
            raise LispError(f"{name}: expected at least 1 argument")
        return unit
    return reduce(fn, nums)


def _sub(*args):
    nums = [_num("-", a) for a in args]
    if not nums:
        raise LispError("-: expected at least 1 argument")
    return -nums[0] if len(nums) == 1 else reduce(lambda a, b: a - b, nums)


def _div(*args):
    nums = [_num("/", a) for a in args]
    if not nums:
        raise LispError("/: expected at least 1 argument")
    if len(nums) == 1:
        nums = [1, nums[0]]
    try:
        result = reduce(lambda a, b: a / b, nums)
    except ZeroDivisionError:
        raise LispError("/: division by zero") from None
    if all(isinstance(n, int) for n in nums) and float(result).is_integer():
        return int(result)
    return result


def _chain(name, test):
    def compare(*args):
        nums = [_num(name, a) for a in args]
        if len(nums) < 2:
            raise LispError(f"{name}: expected at least 2 arguments")
        return all(test(a, b) for a, b in zip(nums, nums[1:]))
    return compare


def _seq(name, x):
    if not isinstance(x, list):
        raise LispError(f"{name}: expected a list, got {write(x)}")
    return x


def _text(name, x):
    if isinstance(x, Symbol) or not isinstance(x, str):
        raise LispError(f"{name}: expected a string, got {write(x)}")
    return x


def _car(x):
    pair = _seq("car", x)
    if not pair:
        raise LispError("car: the empty list has no head")
    return pair[0]


def _cdr(x):
    pair = _seq("cdr", x)
    if not pair:
        raise LispError("cdr: the empty list has no tail")
    return pair[1:]


def _nth(seq, i):
    items = _seq("nth", seq)
    if isinstance(i, bool) or not isinstance(i, int):
        raise LispError("nth: expected an integer index")
    if not 0 <= i < len(items):
        raise LispError(f"nth: index {i} out of range for a list of {len(items)}")
    return items[i]


def _equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, Symbol) != isinstance(b, Symbol):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def _quotient(a, b):
    _num("quotient", a), _num("quotient", b)
    if b == 0:
        raise LispError("quotient: division by zero")
    return int(a / b)                                  # truncate toward zero


def _modulo(a, b):
    _num("modulo", a), _num("modulo", b)
    if b == 0:
        raise LispError("modulo: division by zero")
    return a % b


def _remainder(a, b):
    _num("remainder", a), _num("remainder", b)
    if b == 0:
        raise LispError("remainder: division by zero")
    return a - b * int(a / b)


def _range(*args):
    if not 1 <= len(args) <= 3:
        raise LispError("range: expected 1 to 3 arguments")
    bounds = [_num("range", a) for a in args]
    if any(isinstance(b, float) for b in bounds):
        raise LispError("range: expected integers")
    return list(range(*bounds)) if len(bounds) > 1 else list(range(bounds[0]))


def _sqrt(x):
    n = _num("sqrt", x)
    if n < 0:
        raise LispError("sqrt: expected a non-negative number")
    root = n ** 0.5
    return int(root) if isinstance(n, int) and float(root).is_integer() else root


def _substring(s, start, end=None):
    text = _text("substring", s)
    end = len(text) if end is None else end
    if not (isinstance(start, int) and isinstance(end, int)):
        raise LispError("substring: expected integer bounds")
    if not 0 <= start <= end <= len(text):
        raise LispError(f"substring: bad range {start}..{end} for length {len(text)}")
    return text[start:end]


def _string_ref(s, i):
    text = _text("string-ref", s)
    if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(text):
        raise LispError(f"string-ref: index {write(i)} out of range")
    return text[i]


def _string_to_number(s):
    text = _text("string->number", s).strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return False


def _apply(proc, args):
    return call(proc, _seq("apply", args))


def _map(proc, *seqs):
    lists = [_seq("map", s) for s in seqs]
    if not lists:
        raise LispError("map: expected at least one list")
    return [call(proc, list(group)) for group in zip(*lists)]


def _filter(pred, seq):
    return [x for x in _seq("filter", seq) if truthy(call(pred, [x]))]


def _fold(proc, init, seq):
    acc = init
    for x in _seq("fold", seq):
        acc = call(proc, [acc, x])
    return acc


def _error(*parts):
    raise LispError(" ".join(display(p) for p in parts) or "error")


def _assert(value, *message):
    if not truthy(value):
        note = " ".join(display(m) for m in message)
        raise LispError(f"assertion failed{': ' + note if note else ''}")
    return True


def _display(*args):
    sys.stdout.write("".join(display(a) for a in args))
    return NIL


def _print(*args):
    sys.stdout.write(" ".join(display(a) for a in args) + "\n")
    return NIL


def _newline():
    sys.stdout.write("\n")
    return NIL


def _is_number(x):
    return not isinstance(x, bool) and isinstance(x, (int, float))


def global_env() -> Env:
    env = Env({
        # arithmetic
        "+": lambda *a: _fold_num("+", lambda x, y: x + y, a, 0),
        "-": _sub,
        "*": lambda *a: _fold_num("*", lambda x, y: x * y, a, 1),
        "/": _div,
        "quotient": _quotient,
        "modulo": _modulo,
        "remainder": _remainder,
        "abs": lambda x: abs(_num("abs", x)),
        "min": lambda *a: _fold_num("min", min, a),
        "max": lambda *a: _fold_num("max", max, a),
        "sqrt": _sqrt,
        "expt": lambda a, b: _num("expt", a) ** _num("expt", b),
        # comparison
        "=": _chain("=", lambda a, b: a == b),
        "<": _chain("<", lambda a, b: a < b),
        ">": _chain(">", lambda a, b: a > b),
        "<=": _chain("<=", lambda a, b: a <= b),
        ">=": _chain(">=", lambda a, b: a >= b),
        "not": lambda x: not truthy(x),
        "eq?": lambda a, b: _equal(a, b) if not isinstance(a, list) else a is b,
        "equal?": _equal,
        # lists
        "cons": lambda head, tail: [head] + _seq("cons", tail),
        "car": _car,
        "cdr": _cdr,
        "list": lambda *a: list(a),
        "append": lambda *a: [x for s in a for x in _seq("append", s)],
        "length": lambda s: len(_seq("length", s)),
        "reverse": lambda s: list(reversed(_seq("reverse", s))),
        "nth": _nth,
        "list-ref": _nth,
        "range": _range,
        "apply": _apply,
        "map": _map,
        "filter": _filter,
        "fold": _fold,
        # strings
        "string-append": lambda *a: "".join(_text("string-append", s) for s in a),
        "string-length": lambda s: len(_text("string-length", s)),
        "string-ref": _string_ref,
        "substring": _substring,
        "string=?": lambda a, b: _text("string=?", a) == _text("string=?", b),
        "string<?": lambda a, b: _text("string<?", a) < _text("string<?", b),
        "string>?": lambda a, b: _text("string>?", a) > _text("string>?", b),
        "string->number": _string_to_number,
        "number->string": lambda x: write(_num("number->string", x)),
        "symbol->string": lambda s: str(s) if isinstance(s, Symbol) else
                                    _error("symbol->string: expected a symbol"),
        "string->symbol": lambda s: Symbol(_text("string->symbol", s)),
        # predicates
        "null?": lambda x: isinstance(x, list) and not x,
        "pair?": lambda x: isinstance(x, list) and bool(x),
        "list?": lambda x: isinstance(x, list),
        "number?": _is_number,
        "integer?": lambda x: not isinstance(x, bool) and isinstance(x, int),
        "string?": lambda x: isinstance(x, str) and not isinstance(x, Symbol),
        "symbol?": lambda x: isinstance(x, Symbol),
        "boolean?": lambda x: isinstance(x, bool),
        "procedure?": lambda x: isinstance(x, Lambda) or callable(x),
        "even?": lambda x: _num("even?", x) % 2 == 0,
        "odd?": lambda x: _num("odd?", x) % 2 == 1,
        "zero?": lambda x: _num("zero?", x) == 0,
        # io and control
        "display": _display,
        "newline": _newline,
        "print": _print,
        "write": lambda x: _display(write(x)),
        "error": _error,
        "assert": _assert,
    })
    for name, value in list(env.vars.items()):
        env.vars[Symbol(name)] = value
    for form in parse(PRELUDE):
        evaluate(form, env)
    return env


# ----------------------------------------------------- standard library, in sprout

PRELUDE = r"""
; The rest of the language, written in itself.

(define (caar x) (car (car x)))
(define (cadr x) (car (cdr x)))
(define (cddr x) (cdr (cdr x)))
(define (caddr x) (car (cddr x)))

(defmacro when (test . body)
  `(if ,test (begin ,@body) '()))

(defmacro unless (test . body)
  `(if ,test '() (begin ,@body)))

(defmacro inc! (place . step)
  `(set! ,place (+ ,place ,(if (null? step) 1 (car step)))))

(define (identity x) x)
(define (1+ n) (+ n 1))
(define (1- n) (- n 1))

(define (for-each f xs)
  (unless (null? xs)
    (f (car xs))
    (for-each f (cdr xs))))

(define (last xs)
  (if (null? (cdr xs)) (car xs) (last (cdr xs))))

(define (take xs n)
  (if (or (zero? n) (null? xs))
      '()
      (cons (car xs) (take (cdr xs) (- n 1)))))

(define (drop xs n)
  (if (or (zero? n) (null? xs)) xs (drop (cdr xs) (- n 1))))

(define (sum xs) (fold + 0 xs))
(define (product xs) (fold * 1 xs))

(define (member x xs)
  (cond ((null? xs) #f)
        ((equal? x (car xs)) #t)
        (else (member x (cdr xs)))))

(define (assoc key table)
  (cond ((null? table) #f)
        ((equal? key (caar table)) (car table))
        (else (assoc key (cdr table)))))

(define (any? pred xs)
  (cond ((null? xs) #f)
        ((pred (car xs)) #t)
        (else (any? pred (cdr xs)))))

(define (all? pred xs)
  (cond ((null? xs) #t)
        ((pred (car xs)) (all? pred (cdr xs)))
        (else #f)))

(define (sort xs less?)
  (if (or (null? xs) (null? (cdr xs)))
      xs
      (let ((pivot (car xs)) (rest (cdr xs)))
        (append
          (sort (filter (lambda (x) (less? x pivot)) rest) less?)
          (list pivot)
          (sort (filter (lambda (x) (not (less? x pivot))) rest) less?)))))

(define (string-join parts sep)
  (cond ((null? parts) "")
        ((null? (cdr parts)) (car parts))
        (else (string-append (car parts) sep (string-join (cdr parts) sep)))))

(define (compose f g) (lambda (x) (f (g x))))
"""


# ------------------------------------------------------------------------ main

BANNER = "sprout - a small Lisp. (exit) or Ctrl-D to leave."


def run(src: str, env: Env):
    """Evaluate every form in `src`, returning the last value."""
    result = NIL
    for form in parse(src):
        result = evaluate(form, env)
    return result


def repl(env: Env) -> int:
    print(BANNER)
    buffer = ""
    while True:
        try:
            line = input("... " if buffer else "sprout> ")
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\n(interrupted)")
            buffer = ""
            continue
        buffer = f"{buffer}\n{line}" if buffer else line
        if not buffer.strip():
            buffer = ""
            continue
        if buffer.strip() in ("(exit)", "exit", "(quit)"):
            return 0
        if not complete(buffer):
            continue
        try:
            value = run(buffer, env)
            if value is not NIL and not (isinstance(value, list) and not value):
                print(write(value))
        except LispError as exc:
            print(f"error: {exc}", file=sys.stderr)
        except RecursionError:
            print("error: recursion too deep", file=sys.stderr)
        buffer = ""


def main(argv: list[str]) -> int:
    args = argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(f"usage: {argv[0]} [file.spr ...]   (no arguments starts the REPL)")
        return 0
    env = global_env()
    if not args:
        return repl(env)
    for path in args:
        try:
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 1
        try:
            run(source, env)
        except LispError as exc:
            print(f"{path}: error: {exc}", file=sys.stderr)
            return 1
        except RecursionError:
            print(f"{path}: error: recursion too deep", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.setrecursionlimit(20000)
    sys.exit(main(sys.argv))
