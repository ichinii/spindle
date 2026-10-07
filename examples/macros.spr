; Macros: functions whose arguments are code, and whose result is code.

; `while`, which the language does not have, defined in three lines.
(defmacro while (test . body)
  `(let ((spin '()))
     (set! spin (lambda () (when ,test ,@body (spin))))
     (spin)))

(define i 0)
(define squares '())
(while (< i 6)
  (set! squares (cons (* i i) squares))
  (inc! i))
(print "while loop:" (reverse squares))

; Swap two places. A macro can do this; a function cannot.
(defmacro swap! (a b)
  `(let ((held ,a)) (set! ,a ,b) (set! ,b held)))

(define left 'sinister)
(define right 'dexter)
(swap! left right)
(print "swapped:" left right)

; Threading macros. (-> x (f a)) becomes (f x a) - the value goes in first;
; (->> x (f a)) becomes (f a x) - the value goes in last.
(defmacro -> (x . steps)
  (if (null? steps)
      x
      (let ((step (car steps)))
        `(-> ,(if (list? step)
                  (cons (car step) (cons x (cdr step)))
                  (list step x))
             ,@(cdr steps)))))

(defmacro ->> (x . steps)
  (if (null? steps)
      x
      (let ((step (car steps)))
        `(->> ,(if (list? step)
                   (append step (list x))
                   (list step x))
              ,@(cdr steps)))))

(print "thread first:" (-> 5 (- 1) (* 10)))          ; (* (- 5 1) 10)
(print "thread last: "
       (->> (range 1 11)
            (filter odd?)
            (map (lambda (n) (* n n)))
            sum))

; Macros expand before anything is evaluated, so this never divides by zero.
(defmacro safe-div (a b)
  `(if (zero? ,b) 'undefined (/ ,a ,b)))

(print "safe-div:" (safe-div 10 2) (safe-div 10 0))
