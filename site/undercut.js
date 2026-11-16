// Undercut success model (spec 10). The same maths as scikit-learn:
// p = sigmoid(intercept + sum(coef_i * (x_i - mean_i) / scale_i)), x = [gap, ageB - ageA, ln(lapsLeft)].

export function features(gapS, ageA, ageB, lapsLeft) {
  return [gapS, ageB - ageA, Math.log(Math.max(lapsLeft, 1))];
}

export function predict(params, gapS, ageA, ageB, lapsLeft) {
  const x = features(gapS, ageA, ageB, lapsLeft);
  let z = params.intercept;
  for (let i = 0; i < x.length; i++) z += (params.coef[i] * (x[i] - params.mean[i])) / params.scale[i];
  return 1 / (1 + Math.exp(-z));
}
