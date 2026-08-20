# Institutional Quantitative Research & Theoretical Foundations

This document details the quantitative mathematical frameworks, forensic accounting models, backtest validation theorems, and multi-agent AI research papers implemented within **AI Quant Platform v1.2**.

---

## 1. Quantitative Portfolio & Risk Mathematics

### 1.1 Deflated Sharpe Ratio (DSR) & Probability of Backtest Overfitting (PBO)
- **Reference**: Marcos López de Prado (2014), *Pseudo-Mathematics and Financial Charlatanism*, Notices of the AMS; López de Prado (2018), *Advances in Financial Machine Learning*.
- **Formulation**:
  Given an observed Sharpe ratio \(\widehat{SR}\) derived after testing \(N\) candidate strategy variations over \(T\) observations with skewness \(\gamma_3\) and kurtosis \(\gamma_4\), the expected maximum Sharpe ratio under the null hypothesis of zero true skill is:
  \[
  E[\max_N \{SR_0\}] \approx \left( (1-\gamma) Z^{-1}\left(1 - \frac{1}{N}\right) + \gamma Z^{-1}\left(1 - \frac{1}{N e}\right) \right) \sqrt{V[SR_0]}
  \]
  where \(\gamma \approx 0.5772156649\) is the Euler-Mascheroni constant.
  The Deflated Sharpe Ratio (DSR) computes the probability that the strategy's Sharpe ratio exceeds zero after accounting for selection bias:
  \[
  \text{DSR} = \Phi\left( \frac{(\widehat{SR} - E[\max_N \{SR_0\}]) \sqrt{T-1}}{\sqrt{1 - \gamma_3 \widehat{SR} + \frac{\gamma_4 - 1}{4} \widehat{SR}^2}} \right)
  \]

### 1.2 Combinatorial Purged Cross-Validation (CPCV)
- **Reference**: Marcos López de Prado (2018), *Advances in Financial Machine Learning*, Chapter 12.
- **Formulation**:
  Partitions \(T\) observations into \(N\) groups and tests all \(\binom{N}{k}\) combinations of \(k\) test groups. Training sets are **purged** of labels overlapping with test observations, and an **embargo** period \(h\) is applied post-test to eradicate serial autocorrelation leakage.

### 1.3 Ledoit-Wolf Optimal Shrinkage Covariance Matrix
- **Reference**: Olivier Ledoit and Michael Wolf (2004), *A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices*, Journal of Multivariate Analysis.
- **Formulation**:
  Shrinks the sample covariance matrix \(\mathbf{S}\) towards a structured constant-correlation target \(\mathbf{F}\):
  \[
  \widehat{\Sigma}_{LW} = \delta^* \mathbf{F} + (1 - \delta^*) \mathbf{S}
  \]
  where the optimal shrinkage intensity \(\delta^* \in [0, 1]\) asymptotically minimizes the expected Frobenius loss \(E[\|\widehat{\Sigma} - \Sigma\|_F^2]\).

### 1.4 Half-Kelly Position Sizing & Volatility Targeting
- **Reference**: J. L. Kelly Jr. (1956), *A New Interpretation of Information Rate*, Bell System Technical Journal; Edward O. Thorp (2006).
- **Formulation**:
  \[
  w_{\text{raw}} = \frac{E[R] - R_f}{\sigma^2}, \quad w_{\text{Kelly}} = 0.5 \cdot w_{\text{raw}}
  \]
  Subject to the portfolio volatility target constraint:
  \[
  w_i = \min\left(w_{\text{Kelly}}, \frac{\sigma_{\text{target}}}{\sqrt{w^T \widehat{\Sigma}_{LW} w}} \right)
  \]

---

## 2. Forensic Accounting & Solvency Diagnostics

### 2.1 Canonical 9-Point Piotroski F-Score (2000)
- **Reference**: Joseph D. Piotroski (2000), *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*, Journal of Accounting Research.
- **9 Binary Criteria**:
  1. **Profitability**:
     - \(F_1 = 1\) if \(\text{ROA}_t > 0\)
     - \(F_2 = 1\) if \(\text{CFO}_t > 0\)
     - \(F_3 = 1\) if \(\Delta \text{ROA} = \text{ROA}_t - \text{ROA}_{t-1} > 0\)
     - \(F_4 = 1\) if \(\text{CFO}_t / \text{Assets}_t > \text{ROA}_t\) (Accrual Quality)
  2. **Leverage / Liquidity / Dilution**:
     - \(F_5 = 1\) if \(\Delta \text{Leverage} \le 0\) (Long-term debt to assets)
     - \(F_6 = 1\) if \(\Delta \text{Current Ratio} \ge 0\)
     - \(F_7 = 1\) if \(\text{Shares Outstanding}_t \le \text{Shares Outstanding}_{t-1}\) (Zero dilution)
  3. **Operating Efficiency**:
     - \(F_8 = 1\) if \(\Delta \text{Gross Margin} \ge 0\)
     - \(F_9 = 1\) if \(\Delta \text{Asset Turnover} \ge 0\)
  \[
  F_{\text{Total}} = \sum_{i=1}^9 F_i \quad \in [0, 9]
  \]

### 2.2 Eight-Variable Beneish M-Score (1999)
- **Reference**: Messod G. Beneish (1999), *The Detection of Earnings Manipulation*, Financial Analysts Journal.
- **Formula**:
  \[
  \begin{aligned}
  M = -4.84 &+ 0.920 \cdot \text{DSRI} + 0.528 \cdot \text{GMI} + 0.404 \cdot \text{AQI} + 0.892 \cdot \text{SGI} \\
  &+ 0.115 \cdot \text{DEPI} - 0.172 \cdot \text{SGAI} + 4.679 \cdot \text{TATA} - 0.327 \cdot \text{LVGI}
  \end{aligned}
  \]
  - **Threshold**: \(M > -1.78\) signifies elevated probability of accounting manipulation.
  - **TATA**: Total Accruals to Total Assets computed via balance sheet changes or net cash flow differences.

### 2.3 Edward Altman Z-Score for Public Manufacturing & Service Firms (1968)
- **Reference**: Edward I. Altman (1968), *Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy*, The Journal of Finance.
- **Formula**:
  \[
  Z = 1.2 X_1 + 1.4 X_2 + 3.3 X_3 + 0.6 X_4 + 0.999 X_5
  \]
  where:
  - \(X_1 = \text{Working Capital} / \text{Total Assets}\)
  - \(X_2 = \text{Retained Earnings} / \text{Total Assets}\)
  - \(X_3 = \text{EBIT} / \text{Total Assets}\)
  - \(X_4 = \text{Market Value of Equity} / \text{Total Liabilities}\)
  - \(X_5 = \text{Sales} / \text{Total Assets}\)
  - **Zones**: \(Z \ge 3.0\) Safe, \(1.8 \le Z < 3.0\) Grey, \(Z < 1.8\) Distress.

### 2.4 Richard Sloan Accrual Anomaly (1996)
- **Reference**: Richard G. Sloan (1996), *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?*, The Accounting Review.
- **Formula**:
  \[
  \text{Accruals} = \frac{\text{Net Income} - \text{Operating Cash Flow}}{\text{Average Total Assets}}
  \]

---

## 3. Multi-Asset Telemetry & Cross-Asset Math

### 3.1 24/7 Cryptocurrency Realized Volatility
- **Continuous Clock**: Cryptocurrencies trade 24 hours a day, 365 days a year (8,760 hours/year), unlike traditional equity sessions (252 days \(\times\) 6.5 hours = 1,638 hours/year).
- **Formulation**:
  \[
  \sigma_{\text{Crypto, 30D}} = \text{std}\left( \ln\left(\frac{P_t}{P_{t-1}}\right) \right) \cdot \sqrt{24 \times 365} = \text{std}(\text{log returns}) \cdot \sqrt{8760}
  \]
- **ATH Drawdown %**:
  \[
  \text{DD}_{\text{ATH}} = \left(\frac{P_t}{\text{ATH}} - 1\right) \times 100\%
  \]

### 3.2 Commodity Macro Matrix & Term Structure
- **Gold-to-Silver Ratio**: \(\text{GSR} = P_{\text{Gold}} / P_{\text{Silver}}\)
- **Real Yield Sensitivity**: 3-Year Pearson correlation of commodity returns against 10-Year TIPS yield changes (\(\Delta \text{DFII10}\)):
  \[
  \rho_{\text{RealYield}} = \text{Corr}\left(\frac{\Delta P_{\text{Comm}}}{P_{\text{Comm}}}, \Delta Y_{\text{TIPS}}\right)
  \]
- **10-Year Inflation Beta**:
  \[
  \beta_{\text{Inflation}} = \frac{\text{Cov}(R_{\text{Comm, monthly}}, \Delta \text{YoY CPI})}{\text{Var}(\Delta \text{YoY CPI})}
  \]
- **Futures Roll Yield**:
  \[
  \text{Roll Yield}_{\text{Implied}} = -\left(\frac{F_{\text{Next}}}{F_{\text{Front}}} - 1\right) \times 100\%
  \]

---

## 4. Multi-Agent AI Research & Adversarial Evidence Verification

- **Hubble Framework (2026)**: *An LLM-Driven Agentic Framework for Safe, Diverse, and Reproducible Alpha Factor Discovery* (arXiv:2604.09601). Constrains LLM factor discovery with domain-specific AST expressions evaluated deterministically.
- **XALPHA Architecture (2026)**: *A Memory-Driven AI Quant Researcher for Hypothesis-to-Code Alpha Discovery* (arXiv:2607.08332). Closed-loop research with durable state memory.
- **Adversarial News & Homoglyph Defense (2026)**: *Manipulating Headlines in LLM-Driven Algorithmic Trading* (arXiv:2601.13082). Rigorous input sanitization, Unicode canonicalization (NFKC), and primary vs secondary source hierarchy.
