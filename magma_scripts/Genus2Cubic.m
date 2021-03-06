function divisors_X_0(N,d)
    assert IsPrime(N);
    tors_order := Numerator((N-1)/12);
    X:=SimplifiedModel(ModularCurveQuotient(N,[]));
    ptsX:=Points(X : Bound:=10000);
    P:=Divisor(ptsX[1]);
    Q:=Divisor(ptsX[2]);
    assert IsPrincipal(tors_order*(P-Q)); 
    divisors := [];
    n := tors_order div 2;
    for a in [-n + ((tors_order+1) mod 2)..n] do
       D0 := P+Q+(d-2)*Q + a*(P-Q);
       Append(~divisors, D0);
    end for;
    return divisors,[P,Q];
end function;

function HasRealZero(f)
  for fe in Factorization(f) do;
    r,s := Signature(NumberField(fe[1]));
    if r ne 0 then
      return true;
    end if;
  end for;
  return false;
end function;

function IsTotallyNegative(f)
  //don't want to work with corner cases caused by double roots
  assert IsSquarefree(f);
  if HasRealZero(f) then
    return false;
  end if;
  return Evaluate(f,0) lt 0;
end function;

function MySquarefreePart(f);
  //Modifies f by only dividing f by squares
  squarefree_part := SquarefreePart(f);
  square_part := f div squarefree_part;
  f_sq := f div (GCD(square_part,squarefree_part)^2);
  //this assertion fails if a 4th power divides f
  //error out in this edge case
  assert IsSquarefree(f_sq);
  return f_sq;
end function;

//The folloing computation shows that none of the cubic points on X_0(p) for 
//p=23, 29, 31 are totally real

for p in [23,29,31] do
  divisors, cusps := divisors_X_0(p,3);
  R<x,y> := PolynomialRing(Rationals(),2); 
  for D in divisors do
    if Degree(Reduction(D,&+cusps)) lt 3 then
      //is of the form hyper elliptic + cusp
      continue;
    end if;
    D1,r := Reduction(D,cusps[1]);
    D1 := D1+r*cusps[1];
    V,f := RiemannRochSpace(D1);
    g := f(V.1);
    assert Degree(g) eq 3;
    eq_g := MinimalPolynomial(g);
    A0 := Parent(Coefficients(g)[1]);
    f := eq_g*(A0 ! LCM([Denominator(c) : c in Coefficients(eq_g)]));
    P := Parent(f);
    P0 := Parent(Coefficient(f,0));
    psi0 := hom< P0 -> R | y>;
    psi := hom< P -> R | psi0,[x]>;
    //psi(f) is now an equation for X_0(p) where g, the map of degree 3 is
    //is just the projection on the x coordinate.
    _,disc := IsUnivariate(Discriminant(psi(f),y));
    print p,IsTotallyNegative(MySquarefreePart(disc)),psi(f);
  end for;
end for;
