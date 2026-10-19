# 05 · Semantic similarity of description models

`benchmark_metrics.csv` contains the average CIDEr, BLEURT and ROUGE-L scores of eight
description models over the ten MSVD clips, computed against the Spanish reference descriptions
(paper §5.1–5.2, Fig. 7). "Our model" is the pipeline in `01_semantic_description` (GPT-4o with
CLIP keyframes and attention-guided prompts).

Metrics: CIDEr (Vedantam et al., 2015), BLEURT (Sellam et al., 2020) and ROUGE-L (Lin, 2004).
