; Closures: functions that remember where they came from.

(define (make-counter)
  (let ((n 0))
    (lambda () (inc! n) n)))

(define tick (make-counter))
(define tock (make-counter))          ; its own private n

(tick) (tick) (tick)
(tock)
(print "tick:" (tick) " tock:" (tock))

; A bank account as a message-passing object.
(define (make-account balance)
  (lambda (action . amount)
    (cond ((eq? action 'deposit)  (set! balance (+ balance (car amount))) balance)
          ((eq? action 'withdraw)
           (if (> (car amount) balance)
               "insufficient funds"
               (begin (set! balance (- balance (car amount))) balance)))
          ((eq? action 'balance) balance)
          (else (error "unknown action:" action)))))

(define acct (make-account 100))
(acct 'deposit 50)
(print "after withdrawing 30:" (acct 'withdraw 30))
(print "after withdrawing 500:" (acct 'withdraw 500))
(print "balance:" (acct 'balance))

; Memoisation, built from a closure over an association list.
(define (memoise f)
  (let ((cache '()))
    (lambda (x)
      (let ((hit (assoc x cache)))
        (if hit
            (cadr hit)
            (let ((value (f x)))
              (set! cache (cons (list x value) cache))
              value))))))

(define slow-fib
  (lambda (n) (if (< n 2) n (+ (fib (- n 1)) (fib (- n 2))))))
(define fib (memoise slow-fib))

(print "memoised fib 0..24:" (map fib (range 25)))
