; The obligatory first program.

(define (fizzbuzz n)
  (cond ((zero? (modulo n 15)) "FizzBuzz")
        ((zero? (modulo n 3))  "Fizz")
        ((zero? (modulo n 5))  "Buzz")
        (else (number->string n))))

(print (string-join (map fizzbuzz (range 1 21)) "  "))
