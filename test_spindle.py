#!/usr/bin/env python3
"""Tests for spindle. Run with `python3 test_spindle.py` (or pytest)."""

import sys

from spindle import LispError, Symbol, global_env, parse, run, write

sys.setrecursionlimit(20000)


def ev(src: str):
    """Evaluate source in a fresh environment and return the last value."""
    return run(src, global_env())


def shows(src: str) -> str:
    return write(ev(src))


def raises(src: str) -> str:
    try:
        ev(src)
    except LispError as exc:
        return str(exc)
    raise AssertionError(f"expected an error from: {src}")


# ------------------------------------------------------------------ the reader

def test_reader_atoms():
    assert ev("42") == 42
    assert ev("-7") == -7
    assert ev("3.5") == 3.5
    assert ev("#t") is True
    assert ev("#f") is False
    assert ev('"hi"') == "hi"
    assert ev(r'"a\nb\tc\"d\\e"') == 'a\nb\tc"d\\e'
    assert ev("'sym") == Symbol("sym")
    assert isinstance(ev("'sym"), Symbol)


def test_reader_structure():
    assert ev("'(1 (2 3) ())") == [1, [2, 3], []]
    assert ev("'()") == []
    assert shows("''x") == "(quote x)"
    assert len(parse("(+ 1 2) (+ 3 4) ; trailing comment")) == 2
    assert parse("; only a comment") == []


def test_reader_errors():
    assert "unclosed" in raises("(+ 1 2")
    assert "unexpected ')'" in raises(")")
    assert "unterminated string" in raises('"oops')


# --------------------------------------------------------------- special forms

def test_if_and_truthiness():
    assert ev("(if #t 1 2)") == 1
    assert ev("(if #f 1 2)") == 2
    assert ev("(if 0 'yes 'no)") == Symbol("yes")       # only #f is false
    assert ev("(if '() 'yes 'no)") == Symbol("yes")
    assert ev("(if #f 1)") == []


def test_define_and_set():
    assert ev("(define x 10) (* x x)") == 100
    assert ev("(define (sq n) (* n n)) (sq 9)") == 81
    assert ev("(define x 1) (set! x 5) x") == 5
    assert "not defined" in raises("(set! nope 1)")
    assert "unbound symbol: nope" in raises("nope")


def test_lambda_and_closures():
    assert ev("((lambda (a b) (- a b)) 10 4)") == 6
    counter = """
    (define (make-counter)
      (let ((n 0))
        (lambda () (set! n (+ n 1)) n)))
    (define c (make-counter))
    (c) (c) (c)
    """
    assert ev(counter) == 3
    assert ev("(define c1 ((lambda () 1))) c1") == 1


def test_variadic_lambdas():
    assert ev("((lambda args args) 1 2 3)") == [1, 2, 3]
    assert ev("((lambda (a . rest) rest) 1 2 3)") == [2, 3]
    assert ev("((lambda (a . rest) rest) 1)") == []
    assert "expected 2 args, got 1" in raises("((lambda (a b) a) 1)")
    assert "expected 1+ args, got 0" in raises("((lambda (a . r) a))")


def test_let_forms():
    assert ev("(let ((a 1) (b 2)) (+ a b))") == 3
    assert ev("(let* ((a 1) (b (+ a 1))) (* a b))") == 2
    # plain let sees the outer scope, not its own earlier bindings
    assert ev("(define a 100) (let ((a 1) (b a)) b)") == 100
    assert "bad binding" in raises("(let ((a)) a)")


def test_cond_begin_and_or():
    assert ev("(cond (#f 1) (#t 2) (else 3))") == 2
    assert ev("(cond (#f 1) (else 'fallback))") == Symbol("fallback")
    assert ev("(cond (#f 1))") == []
    assert ev("(cond (42))") == 42                      # clause value when no body
    assert ev("(begin 1 2 3)") == 3
    assert ev("(begin)") == []
    assert ev("(and 1 2 3)") == 3
    assert ev("(and 1 #f (error \"not reached\"))") is False
    assert ev("(and)") is True
    assert ev("(or #f #f 7)") == 7
    assert ev("(or 'first (error \"not reached\"))") == Symbol("first")
    assert ev("(or)") is False


# ---------------------------------------------------------------------- macros

def test_macros():
    assert ev("(when #t 1 2 3)") == 3
    assert ev("(when #f (error \"not reached\"))") == []
    assert ev("(unless #f 'ran)") == Symbol("ran")
    assert ev("(define n 5) (inc! n) (inc! n 10) n") == 16
    swap = """
    (defmacro my-or2 (a b) `(let ((tmp ,a)) (if tmp tmp ,b)))
    (my-or2 #f 'second)
    """
    assert ev(swap) == Symbol("second")


def test_quasiquote():
    assert ev("(define x 2) `(1 ,x 3)") == [1, 2, 3]
    assert ev("(define xs '(2 3)) `(1 ,@xs 4)") == [1, 2, 3, 4]
    assert ev("`(a (b ,(+ 1 1)))") == [Symbol("a"), [Symbol("b"), 2]]
    assert shows("`(1 `(2 ,(+ 1 2)))") == "(1 (quasiquote (2 (unquote (+ 1 2)))))"
    assert "expected a list" in raises("`(1 ,@2)")


# -------------------------------------------------------------------- builtins

def test_arithmetic():
    assert ev("(+ 1 2 3 4)") == 10
    assert ev("(+)") == 0
    assert ev("(*)") == 1
    assert ev("(- 10)") == -10
    assert ev("(- 10 1 2)") == 7
    assert ev("(/ 6 3)") == 2                           # exact when it divides
    assert ev("(/ 7 2)") == 3.5
    assert ev("(/ 4)") == 0.25
    assert ev("(quotient 7 2)") == 3
    assert ev("(quotient -7 2)") == -3                  # truncates toward zero
    assert ev("(modulo 7 2)") == 1
    assert ev("(remainder -7 2)") == -1
    assert ev("(expt 2 10)") == 1024
    assert ev("(sqrt 16)") == 4
    assert ev("(abs -3)") == 3
    assert ev("(max 1 9 2)") == 9
    assert "division by zero" in raises("(/ 1 0)")
    assert "expected a number" in raises('(+ 1 "two")')
    assert "expected a number" in raises("(+ 1 #t)")    # booleans are not ints


def test_comparison_and_equality():
    assert ev("(< 1 2 3)") is True
    assert ev("(< 1 3 2)") is False
    assert ev("(= 2 2.0)") is True
    assert ev("(>= 3 3 2)") is True
    assert ev("(not #f)") is True
    assert ev("(not 0)") is False
    assert ev("(equal? '(1 (2)) '(1 (2)))") is True
    assert ev("(equal? '(1 2) '(1 3))") is False
    assert ev('(equal? "a" \'a)') is False              # string vs symbol
    assert ev("(eq? 'a 'a)") is True
    assert "expected at least 2" in raises("(< 1)")


def test_list_operations():
    assert ev("(cons 1 '(2 3))") == [1, 2, 3]
    assert ev("(car '(1 2))") == 1
    assert ev("(cdr '(1 2 3))") == [2, 3]
    assert ev("(cdr '(1))") == []
    assert ev("(list 1 'a \"s\")") == [1, Symbol("a"), "s"]
    assert ev("(append '(1) '(2 3) '())") == [1, 2, 3]
    assert ev("(length '(1 2 3))") == 3
    assert ev("(reverse '(1 2 3))") == [3, 2, 1]
    assert ev("(nth '(a b c) 1)") == Symbol("b")
    assert ev("(range 3)") == [0, 1, 2]
    assert ev("(range 1 6 2)") == [1, 3, 5]
    assert "empty list has no head" in raises("(car '())")
    assert "out of range" in raises("(nth '(1) 5)")
    assert "expected a list" in raises("(car 7)")


def test_higher_order():
    assert ev("(map (lambda (x) (* x x)) '(1 2 3))") == [1, 4, 9]
    assert ev("(map + '(1 2) '(10 20))") == [11, 22]
    assert ev("(filter odd? (range 1 7))") == [1, 3, 5]
    assert ev("(fold + 0 (range 1 5))") == 10
    assert ev("(apply + '(1 2 3))") == 6
    assert ev("(apply max (list 3 9 1))") == 9
    assert ev("((compose 1+ 1+) 1)") == 3
    assert ev("(procedure? car)") is True
    assert ev("(procedure? (lambda () 1))") is True
    assert "not a procedure" in raises("(42 1)")


def test_strings():
    assert ev('(string-append "a" "b" "c")') == "abc"
    assert ev('(string-length "abc")') == 3
    assert ev('(substring "hello" 1 3)') == "el"
    assert ev('(substring "hello" 3)') == "lo"
    assert ev('(string-ref "abc" 0)') == "a"
    assert ev('(string=? "a" "a")') is True
    assert ev('(string<? "apple" "banana")') is True
    assert ev('(string>? "apple" "banana")') is False
    assert ev('(string->number "42")') == 42
    assert ev('(string->number "x")') is False
    assert ev("(number->string 42)") == "42"
    assert ev("(symbol->string 'abc)") == "abc"
    assert ev('(string->symbol "abc")') == Symbol("abc")
    assert ev('(string-join (list "a" "b" "c") ", ")') == "a, b, c"
    assert "out of range" in raises('(string-ref "abc" 9)')


def test_predicates():
    assert ev("(null? '())") is True
    assert ev("(null? '(1))") is False
    assert ev("(pair? '(1))") is True
    assert ev("(pair? '())") is False
    assert ev("(number? 1)") is True
    assert ev("(number? #t)") is False
    assert ev('(string? "a")') is True
    assert ev("(string? 'a)") is False
    assert ev("(symbol? 'a)") is True
    assert ev("(boolean? #f)") is True
    assert ev("(integer? 1.5)") is False
    assert ev("(even? 4)") is True
    assert ev("(zero? 0)") is True


def test_prelude_library():
    assert ev("(sum (range 1 101))") == 5050
    assert ev("(product '(1 2 3 4))") == 24
    assert ev("(last '(1 2 3))") == 3
    assert ev("(take '(1 2 3 4) 2)") == [1, 2]
    assert ev("(drop '(1 2 3 4) 2)") == [3, 4]
    assert ev("(member 2 '(1 2 3))") is True
    assert ev("(member 9 '(1 2 3))") is False
    assert ev("(assoc 'b '((a 1) (b 2)))") == [Symbol("b"), 2]
    assert ev("(assoc 'z '((a 1)))") is False
    assert ev("(any? odd? '(2 4 5))") is True
    assert ev("(all? odd? '(1 3))") is True
    assert ev("(sort '(3 1 4 1 5 9 2 6) <)") == [1, 1, 2, 3, 4, 5, 6, 9]
    assert ev("(sort '(3 1 2) >)") == [3, 2, 1]
    assert ev("(cadr '(1 2 3))") == 2
    assert ev("(caddr '(1 2 3))") == 3


def test_errors_and_assertions():
    assert "boom" in raises('(error "boom")')
    assert ev("(assert (= 1 1))") is True
    assert "assertion failed: nope" in raises('(assert #f "nope")')


# ------------------------------------------------------------------- the printer

def test_printer():
    assert shows("'(1 2.5 #t #f ())") == "(1 2.5 #t #f ())"
    assert shows('"a\nb"') == '"a\\nb"'
    assert shows("(/ 4 2)") == "2"
    assert shows("(+ 1.0 1.0)") == "2.0"
    assert shows("(list 'a \"a\")") == '(a "a")'
    assert "#<procedure sq>" in shows("(define (sq x) x) sq")
    assert "#<procedure lambda>" in shows("(lambda (x) x)")


# ---------------------------------------------------------- tail call optimisation

def test_tail_calls_do_not_grow_the_stack():
    loop = """
    (define (count-to n acc)
      (if (= n 0) acc (count-to (- n 1) (+ acc 1))))
    (count-to 100000 0)
    """
    assert ev(loop) == 100000


def test_tail_position_in_cond_let_and_begin():
    for form in ("(cond (#t (spin (- n 1))))",
                 "(let ((m n)) (spin (- m 1)))",
                 "(begin 'noise (spin (- n 1)))",
                 "(or #f (spin (- n 1)))",
                 "(when #t (spin (- n 1)))"):
        src = f"""
        (define (spin n)
          (if (= n 0) 'done {form}))
        (spin 50000)
        """
        assert ev(src) == Symbol("done"), form


def test_mutual_recursion_is_also_tail_optimised():
    src = """
    (define (even-length? xs) (if (null? xs) #t (odd-length? (cdr xs))))
    (define (odd-length? xs) (if (null? xs) #f (even-length? (cdr xs))))
    (even-length? (range 30000))
    """
    assert ev(src) is True


# ------------------------------------------------------------------ whole programs

def test_fizzbuzz():
    src = """
    (define (fizzbuzz n)
      (cond ((zero? (modulo n 15)) "FizzBuzz")
            ((zero? (modulo n 3)) "Fizz")
            ((zero? (modulo n 5)) "Buzz")
            (else (number->string n))))
    (map fizzbuzz (range 1 16))
    """
    assert ev(src)[:5] == ["1", "2", "Fizz", "4", "Buzz"]
    assert ev(src)[-1] == "FizzBuzz"


def test_recursive_fib_and_memoised_accumulator():
    assert ev("""
    (define (fib n) (if (< n 2) n (+ (fib (- n 1)) (fib (- n 2)))))
    (map fib (range 10))
    """) == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
    assert ev("""
    (define (fib-fast n a b) (if (zero? n) a (fib-fast (- n 1) b (+ a b))))
    (fib-fast 90 0 1)
    """) == 2880067194370816120


def test_church_style_higher_order_program():
    src = """
    (define (curry f a) (lambda (b) (f a b)))
    (define add5 (curry + 5))
    (map add5 '(1 2 3))
    """
    assert ev(src) == [6, 7, 8]


# ------------------------------------------------------------------------ runner

def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  pass  {name}")
        except AssertionError as exc:
            failures.append((name, f"assertion: {exc}"))
            print(f"  FAIL  {name}")
        except Exception as exc:                        # noqa: BLE001
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  ERROR {name}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed")
    for name, reason in failures:
        print(f"  {name}: {reason}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
