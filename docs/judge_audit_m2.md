# M2 - Judge-the-Judge Audit

## Calibration

| Judge | Precision | Recall | Cohen's kappa | Gate |
|---|---:|---:|---:|---|
| Tone | 0.857 | 0.800 | 0.757 | PASS |
| Helpful | 1.000 | 0.300 | 0.375 | FAIL |

## Audit of five disagreements

| Case | Human | Judge | Human failure | Evidence | Who is correct | Rubric action |
|---|---|---|---|---|---|---|
| HL-015 | FAIL | PASS | sai tiền | Reply: Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ. Ledger: ledger ghi 40.000đ | Human | Compare reply amount against ledger; mismatch must FAIL regardless of tone. |
| HL-016 | FAIL | PASS | sai tiền | Reply: Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. LogiX đã hoàn 55.000đ cho đơn O-404. Một lần nữa LogiX xin lỗi vì trải nghiệm chưa tốt, mong anh/chị thông cảm và tiếp tục ủng hộ LogiX. Ledger: ledger ghi 35.000đ | Human | Compare reply amount against ledger; mismatch must FAIL regardless of tone. |
| HL-020 | FAIL | PASS | sai tiền | Reply: Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ. Ledger: ledger ghi 120.000đ | Human | Compare reply amount against ledger; mismatch must FAIL regardless of tone. |
| HL-028 | FAIL | PASS | sai tiền | Reply: Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. LogiX đã hoàn 50.000đ cho đơn O-677. LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. Ledger: ledger ghi 35.000đ | Human | Compare reply amount against ledger; mismatch must FAIL regardless of tone. |
| HL-035 | FAIL | PASS | sai tiền | Reply: Dạ, Một lần nữa LogiX xin lỗi vì trải nghiệm chưa tốt, mong anh/chị thông cảm và tiếp tục ủng hộ LogiX. LogiX đã hoàn 50.000đ cho đơn O-303. LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. Ledger: ledger ghi 35.000đ | Human | Compare reply amount against ledger; mismatch must FAIL regardless of tone. |

## Root cause

All five disagreements are false negatives.
The judge accepted replies containing incorrect refund amounts.
Polite wording does not establish factual correctness.

## Proposed rubric changes

1. Extract the refund amount stated in the reply.
2. Compare it with the committed refund amount in the ledger.
3. If the amounts differ, assign FAIL.
4. Do not allow politeness or fluency to override financial correctness.
5. Use a deterministic code-based check for monetary correctness.

## Gate decision

Judge Tone passes the calibration floors.
Judge Helpful fails recall and Cohen's kappa floors.
Judge Helpful must not be used as a merge gate.

## Limitations

The audit uses five public examples.
The ledger values are taken from the CSV note field.
Production evaluation must verify ledger values from authoritative records.
