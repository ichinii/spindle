; The Mandelbrot set, in ASCII, with nothing but recursion and floats.

(define max-iter 40)
(define shades (list " " "." ":" "-" "=" "+" "*" "#" "%" "@"))

(define (escape-time cr ci zr zi n)
  (cond ((>= n max-iter) max-iter)
        ((> (+ (* zr zr) (* zi zi)) 4.0) n)
        (else (escape-time cr ci
                           (+ (- (* zr zr) (* zi zi)) cr)
                           (+ (* 2.0 zr zi) ci)
                           (+ n 1)))))

(define (shade n)
  (if (>= n max-iter)
      "@"
      (nth shades (quotient (* n 9) max-iter))))

(define (row x y)
  (if (> x 0.65)
      ""
      (string-append (shade (escape-time x y 0.0 0.0 0))
                     (row (+ x 0.0315) y))))

(define (draw y)
  (when (< y 1.15)
    (print (row -2.05 y))
    (draw (+ y 0.095))))

(draw -1.15)
