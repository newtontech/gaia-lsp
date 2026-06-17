from gaia.engine.lang import claim, register_prior

falsifiable = claim("Heavy bodies and light bodies fall at the same rate in vacuum.")
register_prior(falsifiable, 0.5, justification="Neutral external prior pending measurement.")
