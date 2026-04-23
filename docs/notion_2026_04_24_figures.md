# 2026-04-24 — 成果图补充

> 这份补充只放结果图，不重复正文分析。
> 对应仓库产物目录：`outputs/part1/`、`outputs/part2/`、`outputs/part3/`

---

## Part 1：颈动脉 classical segmentation overlays

![Part 1 classical overlay: p1_20260421_144838_398（gain=83 dB）](../outputs/part1/overlays/p1_20260421_144838_398_overlay.png)

![Part 1 classical overlay: p1_20260421_144929_380（gain=73 dB）](../outputs/part1/overlays/p1_20260421_144929_380_overlay.png)

![Part 1 classical overlay: p1_20260421_144951_958](../outputs/part1/overlays/p1_20260421_144951_958_overlay.png)

![Part 1 classical overlay: p1_20260421_145121_293](../outputs/part1/overlays/p1_20260421_145121_293_overlay.png)

![Part 1 classical overlay: p1_20260421_145210_894](../outputs/part1/overlays/p1_20260421_145210_894_overlay.png)

![Part 1 classical overlay: p1_20260421_145300_800](../outputs/part1/overlays/p1_20260421_145300_800_overlay.png)

![Part 1 classical overlay: p1_20260421_145450_004（color Doppler fallback）](../outputs/part1/overlays/p1_20260421_145450_004_overlay.png)

![Part 1 classical overlay: p1_20260421_145539_147（color Doppler fallback）](../outputs/part1/overlays/p1_20260421_145539_147_overlay.png)

---

## Part 2：classification ROC curves

![Part 2 ROC: full + logistic regression](../outputs/part2/roc_full_logreg.png)

![Part 2 ROC: full + SVM](../outputs/part2/roc_full_svm.png)

![Part 2 ROC: full + random forest](../outputs/part2/roc_full_rf.png)

![Part 2 ROC: cv + logistic regression](../outputs/part2/roc_cv_logreg.png)

![Part 2 ROC: cv + SVM](../outputs/part2/roc_cv_svm.png)

![Part 2 ROC: cv + random forest](../outputs/part2/roc_cv_rf.png)

![Part 2 ROC: refined + logistic regression](../outputs/part2/roc_refined_logreg.png)

![Part 2 ROC: refined + SVM（AUC best among classical custom pipelines）](../outputs/part2/roc_refined_svm.png)

![Part 2 ROC: refined + random forest](../outputs/part2/roc_refined_rf.png)

![Part 2 ROC: BUSAT + logistic regression](../outputs/part2/roc_busat_logreg.png)

![Part 2 ROC: BUSAT + SVM（accuracy best）](../outputs/part2/roc_busat_svm.png)

![Part 2 ROC: BUSAT + random forest（AUC best overall）](../outputs/part2/roc_busat_rf.png)

---

## Part 3：SAM2 on Part 1

![Part 3 SAM2 overlay on Part 1: p1_20260421_144838_398（crop-center fallback failure case）](../outputs/part3/overlays/part1_sam2/p1_20260421_144838_398_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_144929_380（crop-center fallback failure case）](../outputs/part3/overlays/part1_sam2/p1_20260421_144929_380_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_144951_958](../outputs/part3/overlays/part1_sam2/p1_20260421_144951_958_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_145121_293](../outputs/part3/overlays/part1_sam2/p1_20260421_145121_293_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_145210_894](../outputs/part3/overlays/part1_sam2/p1_20260421_145210_894_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_145300_800](../outputs/part3/overlays/part1_sam2/p1_20260421_145300_800_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_145450_004](../outputs/part3/overlays/part1_sam2/p1_20260421_145450_004_overlay.png)

![Part 3 SAM2 overlay on Part 1: p1_20260421_145539_147](../outputs/part3/overlays/part1_sam2/p1_20260421_145539_147_overlay.png)

---

## Part 3：SAM2 on Part 2 representative overlays

![Part 3 SAM2 overlay on Part 2: image 5（low IoU example）](../outputs/part3/overlays/part2_sam2/5_overlay.png)

![Part 3 SAM2 overlay on Part 2: image 26（tiny-mask failure case）](../outputs/part3/overlays/part2_sam2/26_overlay.png)

![Part 3 SAM2 overlay on Part 2: image 117（low IoU example）](../outputs/part3/overlays/part2_sam2/117_overlay.png)

![Part 3 SAM2 overlay on Part 2: image 18（high IoU example）](../outputs/part3/overlays/part2_sam2/18_overlay.png)

![Part 3 SAM2 overlay on Part 2: image 20（high IoU example）](../outputs/part3/overlays/part2_sam2/20_overlay.png)

![Part 3 SAM2 overlay on Part 2: image 82（high IoU example）](../outputs/part3/overlays/part2_sam2/82_overlay.png)

---

## Part 3：foundation-model ROC curves

![Part 3 ROC: OpenCLIP + logistic regression](../outputs/part3/roc/roc_openclip_logreg.png)

![Part 3 ROC: OpenCLIP + SVM](../outputs/part3/roc/roc_openclip_svm.png)

![Part 3 ROC: OpenCLIP + random forest](../outputs/part3/roc/roc_openclip_rf.png)

![Part 3 ROC: BiomedCLIP + logistic regression](../outputs/part3/roc/roc_biomedclip_logreg.png)

![Part 3 ROC: BiomedCLIP + SVM（foundation-model group best）](../outputs/part3/roc/roc_biomedclip_svm.png)

![Part 3 ROC: BiomedCLIP + random forest](../outputs/part3/roc/roc_biomedclip_rf.png)

![Part 3 ROC comparison: logistic regression baseline vs foundation models](../outputs/part3/roc/roc_compare_logreg.png)

![Part 3 ROC comparison: SVM baseline vs foundation models](../outputs/part3/roc/roc_compare_svm.png)

![Part 3 ROC comparison: random forest baseline vs foundation models](../outputs/part3/roc/roc_compare_rf.png)
