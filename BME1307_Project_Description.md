# BME1307 Project 2026 Spring — 项目任务描述

> **报告截止**：2026/6/25 13:00  
> **展示时间**：6/11 与 6/16 课堂，每组 20 分钟（16 分钟汇报 + 4 分钟 Q/A）  
> **组队要求**：3 人一组，每组只需提交一份书面报告，组员同分。

---

## Part 1：超声图像采集与分割（40 分）

### (a) 真实超声图像采集（20 分）
1. **采集对象**：使用便携式超声设备拍摄颈部（左侧或右侧均可）。图像中需清晰可见 **甲状腺区域** 与 **颈动脉（carotid artery）**；气管（trachea）非必需，但有助于定位。  
   *提示：操作前请查阅 Blackboard 上的用户手册。*
2. **参数变化实验**：找到正确位置后，分别在不同 **Gain（增益）** 与 **Dynamic Range（动态范围）** 设置下采集：
   - B-mode 图像
   - Color Doppler 图像
   并在后处理中分析这两个参数的影响。
3. **数据保存**：保存所有图像用于后处理。
4. **记录信息**：记录采集深度等设置，并使用软件自带工具测量并记录颈动脉的直径。

### (b) 图像分割（20 分）
由于健康受试者通常没有异常甲状腺结节，本部分要求对 **B-mode 和/或 Color Doppler 图像中的颈动脉** 进行分割与量化（示例见附件）。
1. **算法实现**：使用课堂所学或自行查阅的任意图像分割技术对颈动脉进行分割并量化。若算法鲁棒性不足，可考虑先裁剪 ROI。
2. **量化与验证**：基于分割结果测量以下指标并与文献对比：
   - 直径（diameter）
   - 面积（area）
   - 圆形相似度（similarity to circle）等  
   参考范围：正常颈总动脉管腔直径约为 **4.3 mm – 7.7 mm**。  
   ⚠️ **关键提示**：必须在数据采集阶段确定 **单个像素对应的实际物理距离**，切勿遗忘！
3. **BUSAT 工具箱适用性**：能否使用 BUSAT toolbox（见 Part 2）分割颈动脉？若能，请实现并解释原因；若不能，请说明理由。

---

## Part 2：超声图像分类（30 分）

本部分可直接使用 **BUSAT toolbox** 中的 `autosegment` 函数辅助分割乳腺超声图像。

- **BUSAT 下载**：[https://www.tamps.cinvestav.mx/~wgomez/downloads.html](https://www.tamps.cinvestav.mx/~wgomez/downloads.html)
- **数据集**：120 例乳腺超声样本及对应标签  
  [https://github.com/Qian-IMMULab/Breast-ultrasound-samples](https://github.com/Qian-IMMULab/Breast-ultrasound-samples)

**任务要求**：
1. **特征提取与选择**：基于分割结果选择/量化特征，随后完成病灶分类任务。
2. **分类方法**：至少实现 **三种** 不同的分类方法，使用 **交叉验证** 策略评估，并报告：
   - 准确率（Accuracy）
   - 敏感度（Sensitivity）
   - 特异度（Specificity）
   - ROC 曲线及 AUC 值
3. **特征数量影响**：所选特征数量是否会影响分类性能？请解释。
4. **分割误差影响**：实际应用中分割误差不可避免。你认为它会影响分类结果吗？请结合实例论证。

---

## Part 3：基础模型驱动的分析（20 分）

近年来，基础模型（foundation models）对医学图像分析产生了深远影响。本部分要求：
1. **调研**：分别调研 **通用基础模型**（generalist foundation models）与 **超声专用基础模型**（ultrasound-specific foundation models）。
2. **评估**：在 **Part 1 的分割任务** 和 **Part 2 的分类任务** 上评估这些模型的性能。
3. **分析**：详细分析其优势与局限性。

> **提示**：为降低计算成本，可直接在无训练或微调（without training or fine-tuning）的情况下评估模型。

---

## Part 4：开放思考题（10 分）

不限于超声领域，回答以下问题：
1. **改进想法**：分享你认为能够改进医学图像处理的具体想法或方法（分割、分类或端到端均可），需要具体说明。
2. **未来方向**：医学图像处理未来的发展方向是什么？对医学应用有何顾虑或担忧？

---

## 附录：推荐 Python 环境

本项目涉及图像处理、传统机器学习以及可能的基础模型推理，建议使用 Python 虚拟环境并安装以下类别的库：
- **图像处理**：`opencv-python`, `Pillow`, `scikit-image`
- **机器学习**：`scikit-learn`
- **深度学习（基础模型评估）**：`torch`, `torchvision`
- **数据分析与可视化**：`numpy`, `pandas`, `matplotlib`, `seaborn`
- **交互开发**：`jupyter`

> 注意：Part 2 中的 `autosegment` 为 **MATLAB 工具箱**，需在 MATLAB 环境中运行；其余任务可在 Python 中完成。
