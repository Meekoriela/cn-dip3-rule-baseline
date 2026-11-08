# Payment calculation scope

[中文](PAYMENT_SCOPE.md)

## Conclusion

**This repository does not and will not provide "enter a case, get a reimbursement or payment amount".** That is not a missing feature; it is a boundary imposed by how DIP payment works. Implementing real-time payment calculation would signal a misunderstanding of the domain.

## Rationale

### 1. The official 3.0 workbook contains no point values

Every worksheet was inspected. The published *DIP 3.0 Grouping Scheme* workbook has 10 sheets and **no column for point values or monetary conversion rates** anywhere. It defines the disease catalogue and grouping rules, not payment rates.

- The national scheme defines how disease groups are formed and assigned.
- Point values for individual disease groups are calculated locally by each pooling region from its own historical cost data; they are local parameters.
- Any implementation claiming to derive point values directly from the national workbook must be hard-coding or inventing local parameters.

This repository therefore treats point values as **external, pluggable parameters**: `extract.py` performs format conversion and indexing only, and neither generates nor infers point values.

### 2. The monetary rate is only fixed at year-end settlement

The DIP point rate (fund amount per point) is, by design:

```
rate = DIP-eligible fund total / total points of all cases in the pooling region
```

Both the numerator (fund total) and the denominator (annual total points) are known only **after the settlement year ends**. During the year:

- the annual case volume and total points are unknown;
- actual fund expenditure, adjustments, and surplus-retention / deficit-sharing settlements are not yet determined;
- therefore no real-time rate exists.

What is legitimate during the year is **parametric estimation**: sensitivity analysis given an assumed rate (or a historical range), explicitly labelled as an estimate, not a settlement result, and not payment advice.

### 3. Group assignment is not settlement

After a case is assigned to a disease group, the actual payment still depends on factors outside the national grouping workbook:

- the pooling region's annual point table and rate;
- high/low cost outliers, special-case review, and ambiguous (QY) groups;
- settlement adjustments such as surplus retention, deficit sharing, and quality assessment;
- deductibles, caps, self-pay items, and insurance-type benefit rules.

Group assignment therefore does not map in one step to a reimbursement amount. This repository stops at structuring the grouping rules and their scope, and does not enter payment calculation.

## What this repository explicitly does not do

1. Receive, store, or process any real patient records (names, encounters, charge details);
2. Embed any point table or rate, or reverse-engineer historical data and present it as a current standard;
3. Output conclusions such as "how much can be reimbursed";
4. Present estimates as determinations made by a medical insurance administration;
5. Claim any official certification or affiliation/authorisation from the publisher.

## If an estimator is added later

The acceptable form is a **parametric sensitivity estimator**, subject to:

- all point values and rates supplied explicitly by the user, with source and applicable year;
- output labelled "estimate, not a settlement result; final determination rests with the competent administration";
- no presence in the decision chain: estimation is downstream analysis and must not affect rule parsing or the 23 assertions;
- consistency with `DATA_NOTICE.md`: official data and derivative artifacts gain no sublicense through an estimator.

## Related documents

- `CODING_STANDARDS.md` — coding-system scope and version policy
- `DATA_NOTICE.md` — provenance, rights and conditions of use
- `../README.md` — project scope, data source and verification system
