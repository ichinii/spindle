; Sorting, and sorting by a key.

(define (merge-sort xs less?)
  (define (merge a b)
    (cond ((null? a) b)
          ((null? b) a)
          ((less? (car b) (car a)) (cons (car b) (merge a (cdr b))))
          (else (cons (car a) (merge (cdr a) b)))))
  (if (or (null? xs) (null? (cdr xs)))
      xs
      (let* ((half (quotient (length xs) 2))
             (left (take xs half))
             (right (drop xs half)))
        (merge (merge-sort left less?) (merge-sort right less?)))))

(define nums '(38 27 43 3 9 82 10))
(print "unsorted:  " nums)
(print "merge sort:" (merge-sort nums <))
(print "quick sort:" (sort nums <))           ; `sort` comes from the prelude
(print "descending:" (sort nums >))

; Sort records by any field.
(define (by key less?)
  (lambda (a b) (less? (cadr (assoc key a)) (cadr (assoc key b)))))

(define people
  (list (list (list 'name "ada")    (list 'born 1815))
        (list (list 'name "grace")  (list 'born 1906))
        (list (list 'name "alan")   (list 'born 1912))
        (list (list 'name "barbara")(list 'born 1926))))

(define (show person)
  (string-append (cadr (assoc 'name person))
                 " (" (number->string (cadr (assoc 'born person))) ")"))

(print "by name:" (string-join (map show (sort people (by 'name string<?))) ", "))
(print "by year:" (string-join (map show (sort people (by 'born <))) ", "))
