# Part 4：开放思考题草稿

> 用途：可直接作为最终课程报告 Part 4 的正文基础；后续迁移到 IEEE LaTeX 时可拆成 `Discussion` / `Future Work` / `Limitations and Clinical Concerns` 小节。

## 4.1 一个具体改进想法：面向临床闭环的“采集感知 + 不确定性驱动”医学图像处理流程

本项目前三部分给出一个很清楚的观察：医学图像处理不应简单理解为“传统方法被基础模型完全替代”。在 Part 1 中，针对颈动脉这一强先验目标，Hough circle、局部对比度打分和 Chan-Vese 细化组成的 classical pipeline 能够在 8 张采集图像上全部得到合理直径，且测得直径均落在正常颈总动脉直径范围内。Part 2 中，BUSAT 基于纹理的分割掩膜与浅层分类器仍然是最强 baseline，其中 `BUSAT + SVM` 的 accuracy 为 0.892，`BUSAT + RF` 的 AUC 为 0.940。Part 3 中，BiomedCLIP embedding 加 SVM 的 AUC 达到 0.935，已经非常接近 BUSAT pipeline；但 SAM2 在颈动脉 zero-shot 分割中对 prompt 质量敏感，只有 6/8 张图的直径落入文献范围。这说明基础模型的表示能力很强，但在低对比、强噪声、设备和操作者差异明显的超声场景中，单靠一个通用模型并不能保证稳定的临床输出。

因此，我认为一个更实际的改进方向是构建“采集感知 + 不确定性驱动”的医学图像处理流程。这个流程不是单一模型，而是一个从图像采集、质量控制、分割、分类、人工复核到模型更新的闭环系统。

第一步是把设备参数和图像本身一起输入模型。超声图像高度依赖 gain、dynamic range、depth、probe frequency、Doppler 设置和操作者手法；同一个解剖结构在不同参数下的灰度分布可能明显变化。传统图像分类常把输入当作一张普通 2D 图像，但在医学超声中，采集参数本身就是影响图像可信度的重要上下文。一个更好的系统应在预处理阶段读取 DICOM 或实验 metadata，把像素间距、扫描深度、增益、动态范围等信息显式用于归一化、质量评分和物理量换算。这样模型输出的不只是 mask 或类别，还包括面积、直径等具有物理单位的指标，并能解释这些指标受采集条件影响的程度。

第二步是采用 hybrid segmentation，而不是在 classical algorithm 和 foundation model 之间二选一。对颈动脉这类形态和位置有强先验的目标，可以先用 Hough circle、管壁对比度或 anatomical ROI 生成候选，再把候选中心、框或粗掩膜作为 prompt 交给 SAM2、MedSAM 或超声基础模型做边界细化。对乳腺病灶这类边界模糊、纹理信息重要的目标，可以把 BUSAT/refined segmentation 作为 teacher mask，用少量人工修正样本做轻量微调或 adapter 训练。这样做的优势是：传统方法负责把搜索空间缩小到医学上合理的位置，基础模型负责吸收大规模预训练得到的边界和语义表示，二者互补而不是互相替代。

第三步是把 uncertainty 作为系统的一等输出。医学图像处理中的错误并不都同等严重：一个低置信度、可被医生快速发现的失败，比一个看似确定但实际错误的输出更安全。具体实现上，可以使用 test-time augmentation、多 prompt ensemble、模型集成或校准后的概率输出，为每个 mask 边界、每个分类结果和每个测量值估计置信区间。当模型对同一病灶的多个 prompt 产生明显不同的 mask，或当分割边界变化会导致分类分数大幅改变时，系统应主动标记为“需要人工复核”，而不是给出单一确定结论。这一点尤其适合超声，因为 speckle noise、阴影、探头压力和切面差异都会造成模型不稳定。

第四步是把医生反馈用于 active learning。临床上完全人工标注所有图像成本很高，但让医生只修正高不确定性、高风险或模型间不一致的病例更可行。系统可以优先收集这些困难样本，用于周期性更新分割 adapter 或分类头，并在每次更新前后进行锁定测试集评估。这样既能降低标注负担，也能让模型把学习能力集中在真实失败模式上。

这个方案对医学图像处理的改进是具体的：它能减少对大规模完整标注的依赖，保留传统方法的物理和解剖先验，同时利用基础模型的泛化表示；它还把“什么时候不该相信模型”纳入流程设计。对本项目而言，后续可以把它落到一个小型原型上：以 Part 1 的 Hough 检测结果作为 SAM2/MedSAM prompt，对不同 gain 和 dynamic range 的图像比较 mask 稳定性；以 Part 2 的 BUSAT mask、refined mask 和 SAM2 mask 构成多分割输入，检查分类器在 mask perturbation 下的 AUC 和校准变化；最后把不确定性最高的样本作为人工复核集合。这比单纯追求某一个模型的最高 AUC 更接近临床部署需要。

## 4.2 未来方向与医学应用顾虑

我认为医学图像处理未来会从“单任务算法”走向“多模态、可交互、可监管的临床辅助系统”。过去的 pipeline 通常围绕一个固定任务展开，例如分割某个器官、检测某种病灶或判断良恶性。未来更有价值的系统应该能同时处理图像、采集参数、既往检查、结构化病历和医生反馈，并输出可复核的证据链，而不是只给出一个类别标签。

第一个方向是医学基础模型的专科化。通用视觉基础模型在自然图像上训练，迁移到医学图像时常受低对比、弱边界和成像物理差异限制。MedSAM、BiomedCLIP 和 USFM 等工作说明，面向医学或特定模态的大规模预训练能够缓解这种问题。对超声而言，真正有价值的 foundation model 不应只学习静态图像纹理，还应学习不同器官、不同探头、不同扫描切面、视频序列和设备参数之间的关系。由于超声强依赖操作者，未来模型甚至可以在采集过程中实时提示“切面不足”“增益过高”“目标未居中”，把 AI 从后处理工具前移到图像采集阶段。

第二个方向是从分类结果走向可量化 biomarkers。临床医生通常不只需要“阳性/阴性”，还需要病灶大小、边界、纵横比、血流、弹性、随访变化等可解释指标。本项目 Part 1 的颈动脉直径、面积、圆形度，以及 Part 2 的形状和纹理特征都属于这类量化信息。未来系统应把分割、测量、分类和随访对比整合到同一个 workflow 中，例如自动给出病灶体积变化、血管狭窄程度、治疗前后响应或恶性风险分层。这样模型输出才能更自然地进入临床决策，而不只是停留在实验指标上。

第三个方向是人机协同和持续学习。医学 AI 很难在一次训练后永久固定，因为设备、协议、人群和疾病谱都会变化。更合理的形式是医生在关键节点参与：模型负责初筛、测量和生成候选解释，医生负责复核高风险或低置信度病例，系统再从这些反馈中改进。监管层面也开始关注 AI 医疗软件更新后的安全性，例如 FDA 针对 AI-enabled device software functions 的 predetermined change control plan 指南，核心就是让模型迭代有预先定义的范围、验证方法和风险控制。

但是，医学应用中必须保持谨慎。

首先是 domain shift 和公平性问题。医学图像模型常在有限中心、有限设备或特定人群上训练，换到新的医院、探头、操作者或患者群体后性能可能下降。超声尤其明显，因为图像质量不只取决于病人，还取决于操作者手法和设备设置。如果模型只在高质量数据上评估，它在基层医院、急诊或床旁场景中的表现可能被高估。因此未来论文和产品都应报告跨设备、跨中心、跨人群的外部验证，而不是只报告随机划分的内部交叉验证。

其次是自动化偏倚。若系统给出的 mask 和诊断分数看起来很确定，医生可能倾向于接受它，即使模型在某些边界模糊或低质量图像上已经失败。医学 AI 的界面设计不应只显示最终结果，还应显示置信度、失败原因、关键图像区域和与历史病例的差异。对于高风险判断，系统应默认作为 second reader 或 triage tool，而不是独立替代医生。

第三是评价指标与真实临床收益之间的差距。AUC、accuracy、Dice 等指标适合算法比较，但不等于患者获益。一个模型即使 AUC 很高，也可能在某些罕见但严重病例上漏诊；一个分割 Dice 很高的模型，也可能在关键边界上产生会影响治疗决策的小误差。因此医学图像处理未来需要更多面向临床结局的评估，例如是否缩短诊断时间、是否减少不必要活检、是否改善随访一致性，以及是否降低不同医生之间的测量差异。

最后是隐私、安全和责任归属。医学影像通常与身份、病史和遗传风险相关，模型训练和部署必须处理数据脱敏、访问权限、网络安全和模型更新记录。若 AI 输出导致错误诊断，责任应如何在模型开发者、医院、设备厂商和临床医生之间划分，目前仍需要清晰制度。对于持续学习系统，还必须防止未经验证的模型更新直接影响临床判断。

总的来说，我认为未来最可靠的医学图像处理路线不是完全自动诊断，而是“可测量、可解释、可拒绝、可监管”的智能辅助。基础模型会成为重要底座，但最终能否进入临床，取决于它是否能和医学成像物理、临床工作流、人工复核机制以及监管要求一起设计。本项目的实验结果也支持这一点：foundation model 已经能在分类上接近传统强 baseline，但在超声分割和临床测量上仍需要解剖先验、采集信息和不确定性控制共同约束。

## 参考来源（后续转 IEEE BibTeX）

1. Jun Ma et al., “Segment anything in medical images,” *Nature Communications*, 2024. https://www.nature.com/articles/s41467-024-44824-z
2. Nikhila Ravi et al., “SAM 2: Segment Anything in Images and Videos,” arXiv:2408.00714, 2024. https://arxiv.org/abs/2408.00714
3. Sheng Zhang et al., “BiomedCLIP: a multimodal biomedical foundation model pretrained from fifteen million scientific image-text pairs,” Microsoft Research / arXiv, 2023. https://www.microsoft.com/en-us/research/publication/biomedclip-a-multimodal-biomedical-foundation-model-pretrained-from-fifteen-million-scientific-image-text-pairs/
4. Jiaqi Chen et al., “USFM: A universal ultrasound foundation model generalized to tasks and organs towards label efficient image analysis,” *Medical Image Analysis*, 2024. https://doi.org/10.1016/j.media.2024.103202
5. U.S. FDA, “Artificial Intelligence-Enabled Medical Devices,” accessed 2026-04-25. https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-aiml-enabled-medical-devices
6. U.S. FDA, “Marketing Submission Recommendations for a Predetermined Change Control Plan for Artificial Intelligence-Enabled Device Software Functions,” Final Guidance, August 2025. https://www.fda.gov/regulatory-information/search-fda-guidance-documents/marketing-submission-recommendations-predetermined-change-control-plan-artificial-intelligence
