# cluster_analysis/theme_graph.py
"""
API-built theme graphs, independent of the library: which genes act on a theme, through which mechanism, and how
they connect. A person's DNA file is cross-referenced afterwards, offline.

    python -m cluster_analysis.theme_graph fertility_female               # → cluster_analysis/theme_graph_fertility_female.json
    python -m cluster_analysis.theme_graph cancer --dna data/input/...     # also → data/output/cluster_analysis/theme_<name>_<theme>.json

Genes      Open Targets: a gene joins when its association with any of the theme's diseases or traits scores ≥ 0.5
           overall, or ≥ 0.5 on human genetic evidence. Mouse-only evidence does not count.
Mechanisms Gene Ontology: a gene sits in a mechanism when it has an experimental or curated human annotation (QuickGO)
           to the mechanism's term or any term below it. Genes without one are grouped by their strongest disease.
Links      STRING interactions (confidence ≥ 0.4) between theme genes, and Reactome pathways shared by theme genes.

The DNA cross-reference runs offline against data/reference (Ensembl gene coordinates, ClinVar, GWAS Catalog):
every SNP in the file that falls inside a theme gene, marked with what is known about it. Only theme names, disease
IDs and gene symbols are sent to the APIs, never anything from the DNA file.
"""
import argparse
import bisect
import csv
import gzip
import io
import json
import os
import re
import zipfile
from collections import defaultdict

from cluster_analysis import sources
from src.loader import imputed_path, iter_calls, person_label

OT_API = "https://api.platform.opentargets.org/api/v4/graphql"
QUICKGO = "https://www.ebi.ac.uk/QuickGO/services/annotation/downloadSearch"
REF = "data/reference"
OUTPUT_DIR = "data/output/cluster_analysis"
TRAITS_PATH = "config/snp_traits.json"
# GO evidence by class. Most behaviour and reproduction biology is known from mouse, so annotations carried over from
# orthologs count too, labelled as such; keyword-mapped electronic annotations are left out.
GO_CLASSES = {
    "human experiment": ["ECO:0000269", "ECO:0000314", "ECO:0000315", "ECO:0000316", "ECO:0000353", "ECO:0000270"],
    "curated": ["ECO:0000304", "ECO:0000305"],
    "from orthologs": ["ECO:0000250", "ECO:0000265", "ECO:0000266", "ECO:0000318"],
}
GO_EVIDENCE = ",".join(e for codes in GO_CLASSES.values() for e in codes)
ECO_CLASS = {e: c for c, codes in GO_CLASSES.items() for e in codes}

THEMES = {
    "fertility_female": {
        "name": "Female fertility",
        "sex": "XX",
        "person": "data/input/MyHeritage_raw_dna_data_XX.csv",
        "about": "The XX reproductive system: desire, the hypothalamus–pituitary signals, the ovaries and their eggs and hormones, "
                 "the fallopian tubes, and the uterus that carries a pregnancy. Built from Open Targets disease genetics and Gene "
                 "Ontology, not from the library.",
        "diseases": {
            "MONDO_0021124": "female infertility", "MONDO_0005387": "primary ovarian failure",
            "MONDO_0018555": "hypogonadotropic hypogonadism", "MONDO_0008487": "polycystic ovary syndrome",
            "MONDO_0005133": "endometriosis", "MONDO_0007886": "uterine fibroids", "MONDO_0006774": "recurrent miscarriage",
            "MONDO_0005081": "preeclampsia", "EFO_0004703": "age at menarche", "EFO_0004704": "age at menopause",
            "EFO_0004697": "estradiol level",
        },
        "measurements": ["age at menarche", "age at menopause", "estradiol level"],
        "pathway_terms": r"Meiosis|Meiotic|Fertilization|Oocyte|Estrogen|Progesterone|Pregnenolone|steroid|Glycoprotein hormones|"
                         r"Hormone ligand-binding|ESR-mediated|Ovarian|Gonadotropin|Prolactin|Oxytocin|Kisspeptin|Peptide hormone",
        "clinvar_terms": r"infertil|hypogonad|ovar|oocyte|estrogen|estradiol|progesterone|pregnan|menstru|menarche|menopaus|puberty|"
                         r"kallmann|aromatase|letrozole|FSH|luteiniz|endometrio|pre-?eclampsia|miscarriage|abortion|uter|leiomyom|"
                         r"polycystic|sex development",
        # Organs drawn on the diagram; mechanisms and diseases place genes on them
        "organs": [
            {"id": "brain", "name": "Brain", "about": "Desire, mating and maternal behaviour."},
            {"id": "pituitary", "name": "Hypothalamus and pituitary", "about": "GnRH from the hypothalamus releases LH and FSH from the pituitary, which run the ovaries."},
            {"id": "ovaries", "name": "Ovaries", "about": "Store and mature eggs, ovulate, and make estrogen and progesterone."},
            {"id": "tubes", "name": "Fallopian tubes", "about": "Carry the egg from the ovary; fertilization happens here."},
            {"id": "uterus", "name": "Uterus", "about": "The muscular wall that grows with and carries a pregnancy."},
            {"id": "endometrium", "name": "Endometrium and placenta", "about": "The lining where the embryo implants and the placenta forms."},
        ],
        "disease_organs": {
            "primary ovarian failure": "ovaries", "polycystic ovary syndrome": "ovaries", "age at menarche": "ovaries",
            "age at menopause": "ovaries", "estradiol level": "ovaries", "hypogonadotropic hypogonadism": "pituitary",
            "endometriosis": "endometrium", "preeclampsia": "endometrium", "recurrent miscarriage": "endometrium",
            "uterine fibroids": "uterus",
        },
        "mechanisms": [
            {"id": "drive", "name": "Desire and maternal behaviour", "go": ["GO:0060180", "GO:0042711", "GO:0019098"],
             "orthologs": True, "organ": "brain", "about": "Female mating behaviour, maternal behaviour and other reproductive behaviour."},
            {"id": "axis", "name": "Hypothalamus–pituitary signals", "go": ["GO:0032274", "GO:0034698", "GO:0043401"],
             "organ": "pituitary", "about": "GnRH, LH and FSH release and response, and steroid hormone receptor signalling."},
            {"id": "hormones", "name": "Estrogen and progesterone production", "go": ["GO:0006703", "GO:0006701", "GO:0120178"],
             "organ": "ovaries", "about": "Making estradiol, progesterone and their precursors."},
            {"id": "ovary", "name": "Ovary development", "go": ["GO:0008585"], "organ": "ovaries",
             "about": "Building the ovaries."},
            {"id": "eggs", "name": "Eggs and follicles", "go": ["GO:0048477", "GO:0001541"], "organ": "ovaries",
             "about": "Oogenesis and follicle growth: how many eggs there are and how they mature."},
            {"id": "cycle", "name": "Ovulation and the cycle", "go": ["GO:0042698", "GO:0030728", "GO:0001553"], "organ": "ovaries",
             "about": "Ovulation, the corpus luteum and the menstrual cycle."},
            {"id": "tubes", "name": "Tubes and fertilization", "go": ["GO:0060066", "GO:0009566"], "organ": "tubes",
             "about": "The oviduct, and sperm meeting egg."},
            {"id": "uterus", "name": "Uterus", "go": ["GO:0060065"], "organ": "uterus", "about": "Building the uterus."},
            {"id": "implantation", "name": "Implantation and decidualization", "go": ["GO:0007566", "GO:0046697"],
             "organ": "endometrium", "about": "The embryo attaching and the lining transforming to receive it."},
            {"id": "pregnancy", "name": "Placenta and pregnancy", "go": ["GO:0007565", "GO:0001890"], "organ": "endometrium",
             "about": "The placenta and carrying a pregnancy."},
        ],
    },
    "fertility_male": {
        "name": "Male fertility",
        "sex": "XY",
        "person": "data/input/MyHeritage_raw_dna_data_XY.csv",
        "about": "The XY reproductive system: desire, the hypothalamus–pituitary signals, the testes and the testosterone and sperm "
                 "they make, sperm maturation and transport, the prostate and seminal vesicles, and erection. Built from Open "
                 "Targets disease genetics and Gene Ontology, not from the library.",
        "diseases": {
            "MONDO_0005372": "male infertility", "MONDO_0004983": "spermatogenic failure", "MONDO_0001913": "oligospermia",
            "HP_0012207": "reduced sperm motility", "MONDO_0009047": "cryptorchidism",
            "MONDO_0018555": "hypogonadotropic hypogonadism", "MONDO_0002146": "hypogonadism",
            "MONDO_0005362": "erectile dysfunction", "EFO_0004908": "testosterone level", "EFO_0004696": "SHBG level",
        },
        "measurements": ["testosterone level", "SHBG level"],
        "pathway_terms": r"Meiosis|Meiotic|Fertilization|Sperm|Acrosome|Androgen|Testosterone|Pregnenolone|steroid|Glycoprotein hormones|"
                         r"Hormone ligand-binding|Gonadotropin|Prolactin|Oxytocin|Kisspeptin|Peptide hormone|Cilium|Axoneme",
        "clinvar_terms": r"infertil|hypogonad|testi[sc]|sperm|azoosperm|oligosperm|testost|androgen|cryptorchid|puberty|kallmann|"
                         r"FSH|luteiniz|SHBG|erectile|sex development|disorder of sex|ciliary dyskinesia",
        "organs": [
            {"id": "brain", "name": "Brain", "about": "Desire and sexual behaviour."},
            {"id": "pituitary", "name": "Hypothalamus and pituitary", "about": "GnRH from the hypothalamus releases LH and FSH from the pituitary, which run the testes."},
            {"id": "testes", "name": "Testes", "about": "Leydig cells make testosterone; Sertoli cells nurse sperm through about 74 days of production."},
            {"id": "epididymis", "name": "Epididymis and vas deferens", "about": "Sperm mature and learn to swim in the epididymis, then travel up the vas deferens."},
            {"id": "prostate", "name": "Prostate and seminal vesicles", "about": "Make most of the seminal fluid that carries and protects sperm."},
            {"id": "penis", "name": "Penis", "about": "Erection and ejaculation."},
        ],
        "disease_organs": {
            "spermatogenic failure": "testes", "oligospermia": "testes", "cryptorchidism": "testes", "hypogonadism": "testes",
            "testosterone level": "testes", "reduced sperm motility": "epididymis", "hypogonadotropic hypogonadism": "pituitary",
            "erectile dysfunction": "penis",
        },
        "mechanisms": [
            {"id": "drive", "name": "Desire and sexual behaviour", "go": ["GO:0060179", "GO:0019098"], "orthologs": True, "organ": "brain",
             "about": "Male mating behaviour and other reproductive behaviour."},
            {"id": "axis", "name": "Hypothalamus–pituitary signals", "go": ["GO:0032274", "GO:0034698", "GO:0043401"], "organ": "pituitary",
             "about": "GnRH, LH and FSH release and response, and steroid hormone receptor signalling."},
            {"id": "hormones", "name": "Testosterone production", "go": ["GO:0006702", "GO:0120178"], "organ": "testes",
             "about": "Making testosterone, DHT and their precursors."},
            {"id": "testis", "name": "Testis development", "go": ["GO:0008584", "GO:0030238", "GO:0033327", "GO:0060009"], "organ": "testes",
             "about": "Building the testis, male sex determination, and Leydig and Sertoli cells."},
            {"id": "sperm", "name": "Sperm production", "go": ["GO:0007283"], "organ": "testes",
             "about": "Spermatogenesis: from stem cell through meiosis to a finished sperm."},
            {"id": "motility", "name": "Sperm maturation and motility", "go": ["GO:0097722", "GO:0030317", "GO:1905867"], "organ": "epididymis",
             "about": "The epididymis, and the tail and energy that let sperm swim."},
            {"id": "fertilization", "name": "Capacitation and fertilization", "go": ["GO:0048240", "GO:0007340", "GO:0009566"],
             "organ": "epididymis", "about": "Capacitation, the acrosome reaction, and binding the egg."},
            {"id": "glands", "name": "Prostate and seminal vesicles", "go": ["GO:0030850", "GO:0061682"], "orthologs": True, "organ": "prostate",
             "about": "Building the glands that make seminal fluid."},
            {"id": "erection", "name": "Erection", "go": ["GO:0043084", "GO:0060406"], "orthologs": True, "organ": "penis",
             "about": "Nitric oxide and smooth-muscle signalling for erection."},
        ],
    },
    "cancer": {
        "name": "Cancer and the life of a cell",
        "person": "data/input/MyHeritage_raw_dna_data_XY.csv",
        "view": "cell",
        "about": "Every cell lives through the same stages: it rests or grows, copies its DNA and divides, passes checkpoints, meets "
                 "toxins and damage, ages, and is meant to die and be cleared. Cancer starts when a cell slips past these controls. "
                 "Genes are placed on the stage they act in, from Gene Ontology, and kept when Open Targets links them to cancer.",
        "diseases": {
            "MONDO_0004992": "cancer", "MONDO_0004989": "breast carcinoma", "MONDO_0005159": "prostate carcinoma",
            "MONDO_0005575": "colorectal cancer", "MONDO_0005138": "lung carcinoma", "MONDO_0005012": "cutaneous melanoma",
            "MONDO_0008170": "ovarian cancer", "MONDO_0005192": "exocrine pancreatic carcinoma", "MONDO_0020804": "basal cell carcinoma",
            "MONDO_0004986": "urinary bladder carcinoma", "MONDO_0005086": "renal cell carcinoma",
        },
        # A mechanism gene stays only with a cancer link of this strength; the GO terms alone cover thousands of genes
        "mechanism_min_disease": 0.3,
        # Joining on disease alone needs human genetic evidence (germline), since somatic tumour evidence says nothing about a DNA file
        "disease_join": "genetic",
        "pathway_terms": r"Cell Cycle|Checkpoint|Mitotic|DNA Replication|DNA Repair|Mismatch|Base Excision|Nucleotide Excision|"
                         r"Homologous|Double-Strand|Fanconi|TP53|p53|Apoptosis|Apoptotic|Caspase|Senescence|Telomer|Oxidative|"
                         r"Detoxification|Biological oxidations|Glutathione|Cytochrome P450|RAS|RAF|MAPK|PI3K|AKT|MTOR|"
                         r"Signaling by (ERBB|EGFR|FGFR|KIT|MET|WNT|Hedgehog|NOTCH|TGF)|Antigen processing|MHC class I",
        "clinvar_terms": r"cancer|carcinoma|tumou?r|neoplas|melanoma|lymphoma|leukemia|sarcoma|polyposis|lynch|li-fraumeni|"
                         r"cowden|von hippel|neurofibromatosis|adenoma|blastoma|glioma|myeloma",
        # Stages of a cell's life, drawn as the cell-cycle diagram; mechanisms place genes on them
        "organs": [
            {"id": "lives", "name": "Living and resting", "about": "Most cells rest (G0) or grow (G1). Growth signals from outside decide "
             "whether a cell starts another round of division, and contact with its neighbours holds it in place."},
            {"id": "birth", "name": "Copying and dividing", "about": "The cell copies its DNA (S phase), prepares (G2) and splits into two "
             "daughter cells (mitosis, M). A round takes about a day in fast-dividing tissue."},
            {"id": "checks", "name": "Checkpoints", "about": "Gates before copying (G1/S), before dividing (G2/M) and during division "
             "(spindle) stop the cycle when DNA is damaged or chromosomes are not attached, until it is fixed."},
            {"id": "stress", "name": "Toxins and damage", "about": "Toxins, radiation and the cell's own oxygen use damage DNA. Enzymes "
             "neutralise toxins and oxidants, and repair systems fix the damage."},
            {"id": "ages", "name": "Ageing", "about": "Each division shortens the telomeres at the chromosome ends. Short telomeres or "
             "lasting damage put the cell into senescence: alive, but never dividing again."},
            {"id": "dies", "name": "Death and clearance", "about": "A cell too damaged to repair kills itself (apoptosis), and the immune "
             "system finds and kills cells that show abnormal proteins."},
            {"id": "escape", "name": "Escape: cancer", "about": "A cell that slips past checkpoints, repair, ageing and death keeps dividing. "
             "To spread it must also break loose from its neighbours and grow its own blood vessels."},
        ],
        "disease_organs": {},
        "mechanisms": [
            {"id": "growth", "name": "Growth signals", "go": ["GO:0007169", "GO:0007265"], "organ": "lives",
             "about": "Growth-factor receptors and the RAS–MAPK and PI3K–AKT relays that tell a cell to divide."},
            {"id": "rest", "name": "Resting and staying in place", "go": ["GO:0044838", "GO:0034332", "GO:0007162"], "organ": "lives",
             "about": "Quiescence, and the cell–cell junctions and adhesion that hold a cell in its tissue."},
            {"id": "replication", "name": "Copying the DNA", "go": ["GO:0006260"], "organ": "birth",
             "about": "DNA replication in S phase."},
            {"id": "division", "name": "Dividing", "go": ["GO:0140014", "GO:0000281", "GO:0044772"], "organ": "birth",
             "about": "Moving through the phases, separating the chromosomes and splitting the cell."},
            {"id": "checkpoints", "name": "Checkpoints", "go": ["GO:0000075"], "organ": "checks",
             "about": "DNA-damage, replication and spindle checkpoints that pause the cycle."},
            {"id": "toxins", "name": "Clearing toxins", "go": ["GO:0006805"], "organ": "stress", "min_disease": 0.1,
             "about": "Phase I and II enzymes that activate and neutralise foreign chemicals: CYPs, GSTs, NAT2, UGTs."},
            {"id": "oxidative", "name": "Oxidative stress", "go": ["GO:0006979"], "organ": "stress", "min_disease": 0.1,
             "about": "Neutralising reactive oxygen and the response to it."},
            {"id": "repair", "name": "DNA repair", "go": ["GO:0006281"], "organ": "stress",
             "about": "Mismatch, base and nucleotide excision, and double-strand break repair."},
            {"id": "telomeres", "name": "Telomeres", "go": ["GO:0000723"], "organ": "ages",
             "about": "Keeping the chromosome ends long: telomerase and the shelterin cap."},
            {"id": "senescence", "name": "Senescence", "go": ["GO:0090398"], "organ": "ages",
             "about": "The permanent stop that ageing or damaged cells enter."},
            {"id": "apoptosis", "name": "Programmed death", "go": ["GO:0097193", "GO:0097191"], "organ": "dies",
             "about": "The internal (mitochondrial) and external (death receptor) routes to apoptosis."},
            {"id": "immune", "name": "Immune clearance", "go": ["GO:0002474", "GO:0001913", "GO:0042267"], "organ": "dies",
             "about": "Showing protein fragments on MHC class I, and the T and NK cells that kill abnormal cells."},
            {"id": "spread", "name": "Invasion and new blood vessels", "go": ["GO:0001837", "GO:0001525"], "organ": "escape",
             "about": "Epithelial–mesenchymal transition, which lets a cell break loose, and angiogenesis, which feeds a tumour."},
        ],
        "disease_explain": "Open Targets ties these genes to cancer through human genetics (GWAS and inherited variants), but Gene Ontology "
                           "places them on none of the cell's stages yet. Many are risk loci near a gene whose role is still unclear.",
    },
}

# What each mechanism means and how a change in it plays out; shown in the explorer's in-depth view
EXPLAIN = {
    "fertility_female": {
        "drive": "Desire and bonding run on brain signalling: oxytocin and its receptor (OXTR) for bonding and maternal care, dopamine and "
                 "serotonin for motivation and mood, and sex hormones acting on the hypothalamus. Variants here shift how strongly these "
                 "signals land, not whether the system works.",
        "axis": "The hypothalamus releases GnRH in pulses, and the pituitary answers with LH and FSH, which make the ovaries grow follicles, "
                "ovulate and make hormones. Estrogen and progesterone feed back to tune the pulses. Weaker receptors (FSHR, LHCGR) or hormone "
                "subunits (FSHB) change how hard the ovaries are driven, and the timing of puberty and menopause.",
        "hormones": "Theca cells turn cholesterol into androgens (StAR, CYP11A1, CYP17A1), and granulosa cells convert them to estradiol with "
                    "aromatase (CYP19A1). After ovulation the corpus luteum makes progesterone to prepare the lining. Changes here shift "
                    "hormone levels across the cycle.",
        "ovary": "Genes that build the ovary and keep its supporting cells female (FOXL2, NR5A1, WNT4). Broken copies cause early ovarian "
                 "failure; common variants have small effects on egg reserve and menopause timing.",
        "eggs": "Eggs are made before birth and stored in follicles. Each cycle a group grows and usually one matures. Genes here set the "
                "size of the egg reserve (AMH signalling, GDF9, BMP15), the quality of meiosis and how fast follicles are used up, which "
                "shapes the fertile window and menopause age.",
        "cycle": "The LH surge triggers ovulation, the emptied follicle becomes the corpus luteum, and its progesterone holds the lining. "
                 "Genes here shape cycle regularity, ovulation and the luteal phase; several PCOS genes sit here.",
        "tubes": "The fallopian tube catches the egg, moves it with cilia and muscle, and is where sperm meets egg. Genes here cover tube "
                 "development, sperm–egg binding and early embryo transport.",
        "uterus": "Genes that build the uterus (HOXA10, HOXA11, WNT signalling). Variants here link to uterine shape, fibroids and the muscle "
                  "that carries and delivers a pregnancy.",
        "implantation": "Under progesterone the lining transforms (decidualization) and opens a short window in which the embryo can "
                        "attach. Genes here (PGR, HOXA10, LIF signalling) affect implantation and recurrent miscarriage.",
        "pregnancy": "The placenta grows from the embryo into the lining, remodels the mother's arteries and manages blood flow, hormones "
                     "and immune tolerance. Genes here link to preeclampsia, fetal growth and pregnancy loss.",
    },
    "fertility_male": {
        "drive": "Desire runs on testosterone acting in the brain, dopamine reward signalling and oxytocin. GO's male mating behaviour genes "
                 "come mostly from mouse studies. Variants here shift intensity, not whether drive is there.",
        "axis": "GnRH pulses from the hypothalamus release LH and FSH. LH makes Leydig cells produce testosterone; FSH, together with "
                "testosterone, drives Sertoli cells to support sperm production. Testosterone and inhibin feed back. Changes here link to "
                "hypogonadism and lower sperm counts; the FSHB −211 variant lowers FSH, for example.",
        "hormones": "Leydig cells turn cholesterol into testosterone (StAR, CYP11A1, CYP17A1, HSD17B3). SRD5A2 converts some into the "
                    "stronger DHT, and aromatase turns some into estradiol. SHBG in the blood decides how much is free. Variants here move "
                    "testosterone levels.",
        "testis": "Genes that make the testis and keep it male (SRY, SOX9, NR5A1), and that build the Leydig and Sertoli cells. Strong "
                  "defects cause differences of sex development and undescended testes.",
        "sperm": "Making a sperm takes about 74 days: stem cells divide, go through meiosis and remodel into sperm, nursed by Sertoli cells. "
                 "Hundreds of genes take part, so most male-infertility genes sit here; variants link to low or absent sperm counts.",
        "motility": "Sperm swim with a tail (flagellum) powered by mitochondria, and gain that ability while they mature in the epididymis. "
                    "Genes here cover the tail, its energy supply and maturation; defects cause poor motility.",
        "fertilization": "In the female tract sperm capacitate, then the acrosome reaction releases enzymes that cut through the egg's coat "
                         "before the sperm binds and fuses. Genes here cover those steps.",
        "glands": "The prostate and seminal vesicles make most of the seminal fluid and its enzymes, which protect sperm and liquefy the "
                  "ejaculate. Genes here cover the glands' development.",
        "erection": "Erection needs nitric oxide from nerves and the vessel lining (NOS3), cGMP signalling in the smooth muscle (broken down "
                    "by PDE5), and good blood flow. Genes here link to erectile dysfunction, which shares risk with blood vessel health.",
    },
    "cancer": {
        "growth": "Growth factors bind receptors on the surface (EGFR, ERBB2, FGFR, KIT), which pass the signal through RAS, RAF and MAPK, "
                  "or PI3K, AKT and mTOR, to switch on the genes for division. PTEN and NF1 are brakes on these relays. A relay stuck "
                  "on (a more active oncogene) or a brake lost (a less active PTEN or NF1) lets a cell divide without being told to.",
        "rest": "Most cells in an adult are resting, held in their place by junctions with their neighbours (cadherins such as CDH1, "
                "and catenins). Contact with neighbours also tells a cell to stop dividing. Losing these contacts is an early step "
                "towards invasion; inherited CDH1 loss causes stomach and breast cancer.",
        "replication": "In S phase the whole genome is copied once. Polymerases with proofreading (POLE, POLD1) and the licensing system "
                       "that stops a second round make it accurate. Weaker proofreading leaves more mutations behind in every division.",
        "division": "Cyclins and CDKs move the cell from phase to phase, and RB1 holds the gate at G1 until the cell is ready. In mitosis "
                    "the chromosomes are attached to the spindle and pulled apart. Losing RB1 or the CDK inhibitors (CDKN2A) lets cells "
                    "cycle unchecked; missegregation gives daughter cells the wrong number of chromosomes.",
        "checkpoints": "ATM and ATR sense broken or stalled DNA and, through CHEK1, CHEK2 and p53 (TP53), stop the cycle until it is "
                       "repaired, or send the cell to die. The spindle checkpoint (BUB1, MAD2) holds division until every chromosome is "
                       "attached. These are the guards cancer most often disables: TP53 is mutated in about half of all tumours, and "
                       "inherited CHEK2 and ATM variants raise breast and prostate cancer risk.",
        "toxins": "Phase I enzymes (CYP1A1, CYP1B1, CYP2E1) make foreign chemicals easier to remove, but often make them more reactive "
                  "first; phase II enzymes (GSTM1, GSTP1, NAT2, UGTs) attach a tag that neutralises and clears them. The balance "
                  "between the two decides how much of a carcinogen from smoke, grilled meat or solvents reaches DNA. Slow NAT2 and "
                  "missing GSTM1 are the classic examples, raising bladder cancer risk in smokers.",
        "oxidative": "Using oxygen for energy leaks superoxide and peroxide, which damage DNA, fats and proteins. SOD2, catalase, "
                     "glutathione peroxidases and NRF2 (NFE2L2) neutralise them. Weaker defences mean more oxidative DNA damage over "
                     "time.",
        "repair": "Different systems fix different damage: mismatch repair (MLH1, MSH2, MSH6, PMS2) corrects copying errors, base excision "
                  "(OGG1, MUTYH) fixes oxidised bases, nucleotide excision (XPC, ERCC2) removes UV and chemical damage, and homologous "
                  "recombination (BRCA1, BRCA2, PALB2) repairs double-strand breaks. Inherited loss of one copy is the cause of Lynch "
                  "syndrome and hereditary breast and ovarian cancer; common variants have small effects.",
        "telomeres": "Telomeres cap the chromosome ends and shorten with each division, which limits how often a cell can divide. "
                     "Telomerase (TERT, TERC) rebuilds them in stem cells. Cancers switch telomerase back on to divide forever; TERT "
                     "variants are among the strongest common risk loci for many cancers, and long telomeres raise risk for some.",
        "senescence": "When telomeres run short or damage persists, p53, p21 (CDKN1A) and p16 (CDKN2A) put the cell into permanent arrest. "
                      "This is a barrier against cancer, but senescent cells also release inflammatory signals that, over the years, "
                      "can feed the growth of nearby cells.",
        "apoptosis": "A cell too damaged to save dismantles itself. In the internal route p53 and BH3 proteins open the mitochondria (BAX, "
                     "BAK) against the guards BCL2 and MCL1, releasing cytochrome c to start the caspases. In the external route death "
                     "receptors (FAS, TNFRSF10) start them from outside. Tumours often raise BCL2 or lose BAX to survive.",
        "immune": "Every cell shows fragments of its proteins on MHC class I (HLA, B2M, TAP1). Cytotoxic T cells recognise abnormal "
                  "fragments from mutated proteins, and NK cells kill cells that hide their MHC. Tumours escape by losing B2M or HLA, or "
                  "by raising PD-L1, which is what immunotherapy reverses.",
        "spread": "To spread, a tumour cell drops its junctions and becomes mobile (epithelial–mesenchymal transition, driven by SNAI1, "
                  "TWIST1, ZEB1), digests its surroundings (MMPs), and grows its own blood supply (VEGFA and its receptors). These are "
                  "late steps; variants here matter more for how a cancer behaves than for whether it starts.",
    },
}
DISEASE_EXPLAIN = ("Open Targets ties these genes to one of the theme's conditions, mostly through GWAS, but Gene Ontology has no "
                   "reproductive mechanism for them yet. Treat them as signals to follow up rather than explained pathways.")


# --- Open Targets ------------------------------------------------------------------------------------

def _gql(query, variables):
    r = sources._request("POST", OT_API, json={"query": query, "variables": variables}, timeout=180) or {}
    if r.get("errors"):
        raise RuntimeError(r["errors"][0].get("message", "Open Targets error"))
    return r["data"]


def ot_targets(disease_id):
    """Every gene associated with a disease: overall score and per-evidence-type scores."""
    q = """query($id:String!,$i:Int!){disease(efoId:$id){name descendants associatedTargets(page:{index:$i,size:3000}){
           count rows{score target{approvedSymbol} datatypeScores{id score}}}}}"""
    def fetch():
        out, i = {"descendants": [], "rows": []}, 0
        while True:
            d = _gql(q, {"id": disease_id, "i": i})["disease"]
            if not d:
                return out
            out["descendants"] = d.get("descendants") or []
            out["rows"] += [{"gene": r["target"]["approvedSymbol"], "score": r["score"],
                             "types": {x["id"]: x["score"] for x in r["datatypeScores"]}} for r in d["associatedTargets"]["rows"]]
            if len(out["rows"]) >= d["associatedTargets"]["count"]:
                return out
            i += 1
    return sources._cached("ot_targets", disease_id, fetch)


# --- Gene Ontology (QuickGO) -----------------------------------------------------------------------

def go_genes(go_id):
    """{symbol: [(GO term name, evidence class)]} for human genes annotated to a GO term or any term below it."""
    def fetch():
        r = sources.requests.get(QUICKGO, params={"goId": go_id, "goUsage": "descendants", "goUsageRelationships": "is_a,part_of,occurs_in",
                                                 "taxonId": "9606", "geneProductType": "protein", "evidenceCode": GO_EVIDENCE,
                                                 "evidenceCodeUsage": "descendants", "downloadLimit": 50000,
                                                 "selectedFields": "symbol,goId,goName,evidenceCode", "includeFields": "goName"},
                                 headers={"Accept": "text/tsv"}, timeout=300)
        r.raise_for_status()
        return [[x["SYMBOL"], x["GO NAME"], x["ECO ID"]] for x in csv.DictReader(io.StringIO(r.text), delimiter="\t")]
    out = defaultdict(set)
    for sym, name, eco in sources._cached("quickgo_genes2", go_id + "|" + GO_EVIDENCE, fetch):
        out[sym].add((name, ECO_CLASS.get(eco, "other")))
    return out


# --- Build --------------------------------------------------------------------------------------------

def build(theme_id):
    """Theme genes = mechanism genes (Gene Ontology) ∪ disease genes (Open Targets), each with both kinds of evidence."""
    theme = THEMES[theme_id]
    measured = set(theme.get("measurements", ()))
    rank = list(GO_CLASSES) + ["other"]

    # Open Targets: every association ≥ 0.2 is kept as evidence; the stricter rule decides who joins on disease alone
    assoc, by_disease, disease_ids = defaultdict(dict), defaultdict(set), {}
    keep = min([0.2] + [m["min_disease"] for m in theme["mechanisms"] if m.get("min_disease")])
    for did, label in theme["diseases"].items():
        t = ot_targets(did)
        disease_ids[did] = [did] + t["descendants"]
        need = 0.8 if label in measured else 0.5
        for r in t["rows"]:
            genetic = r["types"].get("genetic_association", 0)
            if r["score"] >= keep or genetic >= 0.2:
                assoc[r["gene"]][label] = {"score": round(r["score"], 3), "genetic": round(genetic, 3),
                                           "types": sorted(k for k, v in r["types"].items() if v >= 0.1)}
            # Germline themes join on human genetics only; others on the overall score too
            joins = genetic >= need if theme.get("disease_join") == "genetic" else (r["score"] >= 0.5 or genetic >= need)
            if joins:
                by_disease[r["gene"]].add(label)

    # Gene Ontology: human or curated annotations always count; ortholog-only ones when the mechanism says so,
    # or when the gene also has a fertility association
    mech = defaultdict(dict)
    for m in theme["mechanisms"]:
        for go_id in m["go"]:
            for sym, terms in go_genes(go_id).items():
                mech[sym].setdefault(m["id"], set()).update(terms)
    genes = {}
    for sym in set(by_disease) | set(mech):
        mechanisms = {}
        for mid, terms in mech.get(sym, {}).items():
            best = min((c for _, c in terms), key=rank.index)
            m = next(x for x in theme["mechanisms"] if x["id"] == mid)
            if best in ("human experiment", "curated") or (best == "from orthologs" and (m.get("orthologs") or assoc.get(sym))):
                mechanisms[mid] = {"terms": sorted({n for n, _ in terms})[:4], "evidence": best}
        diseases = assoc.get(sym, {})
        floor = theme.get("mechanism_min_disease")
        if floor and sym not in by_disease:
            # A stage gene needs a link to the theme's diseases too; detox and antioxidant genes, known mostly from
            # older candidate-gene studies, need a weaker one
            top = max((d["score"] for d in diseases.values()), default=0)
            by_id = {m["id"]: m for m in theme["mechanisms"]}
            mechanisms = {k: v for k, v in mechanisms.items() if top >= by_id[k].get("min_disease", floor)}
        if not mechanisms and sym not in by_disease:
            continue
        best = max(diseases, key=lambda d: diseases[d]["score"]) if diseases else None
        # Organs: from the gene's mechanisms, and from diseases it is strongly linked to
        mech_organ = {m["id"]: m.get("organ") for m in theme["mechanisms"]}
        organs = {mech_organ[m] for m in mechanisms if mech_organ.get(m)}
        organs |= {theme.get("disease_organs", {}).get(d) for d in by_disease.get(sym, ())} - {None}
        genes[sym] = {"mechanisms": mechanisms, "diseases": diseases, "joined_by": sorted(by_disease.get(sym, ())),
                      "organs": sorted(organs),
                      "primary": next((m["id"] for m in theme["mechanisms"] if m["id"] in mechanisms), None),
                      "best_disease": best, "best_score": diseases[best]["score"] if best else 0}
    print(f"   {len(genes)} genes: {sum(1 for g in genes.values() if g['mechanisms'])} with a mechanism, "
          f"{sum(1 for g in genes.values() if g['joined_by'])} on disease evidence")

    # Shared Reactome pathways, offline: GTF symbol → Ensembl gene → lowest-level human pathways
    ensg = {}
    with gzip.open(f"{REF}/ensembl_grch37_genes.gtf.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if "\tgene\t" in line:
                m = re.search(r'gene_id "([^"]+)".*?gene_name "([^"]+)"', line)
                if m and m.group(2) in genes:
                    ensg[m.group(1)] = m.group(2)
    members = defaultdict(set)
    with open(f"{REF}/Ensembl2Reactome.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 6 and p[5] == "Homo sapiens" and p[0] in ensg:
                members[p[3]].add(ensg[p[0]])
    on_theme = re.compile(theme.get("pathway_terms", "$^"), re.I)
    pathways = sorted(({"pathway": k, "genes": sorted(v), "on_theme": bool(on_theme.search(k))} for k, v in members.items()
                       if len(v) >= 3), key=lambda x: (not x["on_theme"], -len(x["genes"])))[:80]

    symbols = sorted(genes)
    edges = sources.string_network(symbols, required_score=400) if len(symbols) <= 2000 else []
    links = list({tuple(sorted((e["preferredName_A"], e["preferredName_B"]))): {"a": e["preferredName_A"], "b": e["preferredName_B"],
                  "score": e["score"]} for e in edges if e["preferredName_A"] in genes and e["preferredName_B"] in genes}.values())
    rule = ("Gene Ontology mechanism genes, plus Open Targets genes scoring ≥ 0.5 (≥ 0.8 genetic for level and timing traits)"
            if not theme.get("mechanism_min_disease") else
            f"Gene Ontology stage genes with an Open Targets cancer score ≥ {theme['mechanism_min_disease']}, plus genes with "
            "human genetic evidence ≥ 0.5 for a cancer")
    return {"theme": theme_id, "name": theme["name"], "about": theme["about"], "rule": rule, "view": theme.get("view"),
            "diseases": theme["diseases"], "disease_ids": disease_ids,
            "mechanisms": [{**{k: m.get(k) for k in ("id", "name", "about", "go", "organ")},
                            "explain": EXPLAIN.get(theme_id, {}).get(m["id"])} for m in theme["mechanisms"]],
            "disease_explain": theme.get("disease_explain", DISEASE_EXPLAIN),
            "organs": theme.get("organs", []), "disease_organs": theme.get("disease_organs", {}), "sex": theme.get("sex"),
            "person": theme.get("person"),
            "genes": dict(sorted(genes.items())), "links": links, "pathways": pathways}


# --- Offline cross-reference with a DNA file ---------------------------------------------------------

def gene_regions(symbols, flank=5000):
    """{chrom: [(start, end, symbol)]} from the Ensembl GRCh37 GTF, with a flank for promoters and nearby regulation."""
    out = defaultdict(list)
    with gzip.open(f"{REF}/ensembl_grch37_genes.gtf.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.split("\t", 9)
            if len(p) < 9 or p[2] != "gene":
                continue
            m = re.search(r'gene_name "([^"]+)"', p[8])
            if m and m.group(1) in symbols:
                out[p[0]].append((int(p[3]) - flank, int(p[4]) + flank, m.group(1)))
    return out


def clinvar_index(rsids):
    """{rsid: [{significance, condition, ref, alt}]} for the given rsIDs from the GRCh37 ClinVar VCF."""
    out = defaultdict(list)
    with gzip.open(f"{REF}/clinvar_grch37.vcf.gz", "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            m = re.search(r"RS=(\d+)", p[7])
            if not m or "rs" + m.group(1) not in rsids:
                continue
            info = dict(x.split("=", 1) for x in p[7].split(";") if "=" in x)
            out["rs" + m.group(1)].append({"significance": info.get("CLNSIG", "").replace("_", " "),
                                           "condition": info.get("CLNDN", "").replace("_", " ").split("|")[0],
                                           "ref": p[3], "alt": p[4]})
    return out


def gwas_index(rsids, trait_ids, known=None):
    """{rsid: [{trait, risk_allele, p, pubmed}]} for associations of the given rsIDs with the theme's traits.

    known, when given, is filled with {rsid: [{allele, trait, direction}]} from every genome-wide significant study of
    those SNPs that names its allele, whatever the trait: it explains associations whose study left the allele out."""
    out = defaultdict(list)
    with zipfile.ZipFile(f"{REF}/gwas_associations_ontology.zip") as z:
        name = next(n for n in z.namelist() if n.endswith((".tsv", ".txt")))
        with z.open(name) as f:
            for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t"):
                uris = {u.rsplit("/", 1)[-1] for u in (row.get("MAPPED_TRAIT_URI") or "").split(",")}
                if known is not None and not uris & trait_ids:
                    allele = (row.get("STRONGEST SNP-RISK ALLELE") or "").split("-")[-1].strip()
                    hits = [rs for rs in re.findall(r"rs\d+", row.get("SNPS", "")) if rs in rsids]
                    if hits and len(allele) == 1 and allele in "ACGT":
                        try:
                            ok = float(row.get("P-VALUE") or 1) <= 5e-8
                        except ValueError:
                            ok = False
                        ci = (row.get("95% CI (TEXT)") or "").lower()
                        try:
                            effect = float(row.get("OR or BETA") or "nan")
                        except ValueError:
                            effect = float("nan")
                        direction = "raises" if "increase" in ci else "lowers" if "decrease" in ci else \
                            ("raises" if effect > 1 else "lowers" if effect < 1 else None) if effect == effect and effect > 0 else None
                        if ok and direction:
                            for rs in hits:
                                known[rs].append({"allele": allele, "trait": row.get("MAPPED_TRAIT") or row.get("DISEASE/TRAIT"),
                                                  "direction": direction})
                if not uris & trait_ids:
                    continue
                for rs in re.findall(r"rs\d+", row.get("SNPS", "")):
                    if rs in rsids:
                        risk = (row.get("STRONGEST SNP-RISK ALLELE") or "").split("-")[-1].strip()
                        try:
                            p = float(row.get("P-VALUE") or 1)
                        except ValueError:
                            p = 1.0
                        if p > 5e-8:
                            continue
                        ci = (row.get("95% CI (TEXT)") or "").lower()
                        try:
                            effect = float(row.get("OR or BETA") or "nan")
                        except ValueError:
                            effect = float("nan")
                        # Levels report a beta with "unit increase/decrease"; diseases an odds ratio
                        direction = "raises" if "increase" in ci else "lowers" if "decrease" in ci else \
                            ("raises" if effect > 1 else "lowers" if effect < 1 else None) if effect == effect and effect > 0 else None
                        out[rs].append({"trait": row.get("MAPPED_TRAIT") or row.get("DISEASE/TRAIT"), "study": row.get("DISEASE/TRAIT"),
                                        "risk_allele": risk, "p": p, "pubmed": row.get("PUBMEDID"), "direction": direction,
                                        "effect": effect if effect == effect else None,
                                        "kind": "beta" if "unit" in ci else "odds ratio" if effect == effect else None})
    return out


# Imputed calls (src/impute.py) carry a confidence tier. Findings use the trustworthy ones; a pathogenic variant
# counts as carried only when measured or imputed at high confidence, and weaker carrier calls are listed as possible.
FINDING_TIERS = {"measured", "high", "medium"}
CARRIED_TIERS = {"measured", "high"}


def in_regions(regions):
    """A lookup chrom, pos -> [gene symbols] over gene_regions(), by binary search."""
    index = {}
    for chrom, spans in regions.items():
        spans = sorted(spans)
        index[chrom] = ([s for s, _, _ in spans], spans, max(e - s for s, e, _ in spans))

    def genes_at(chrom, pos):
        if chrom not in index:
            return ()
        starts, spans, longest = index[chrom]
        hi = bisect.bisect_right(starts, pos)
        lo = bisect.bisect_left(starts, pos - longest)
        return [sym for s, e, sym in spans[lo:hi] if e >= pos]
    return genes_at


FLIP = str.maketrans("ACGT", "TGCA")


def clinvar_copies(gt, ref, alts):
    """Copies of a ClinVar record's alternative allele(s) in a forward-strand genotype.

    One position often has several ClinVar records, one per possible change (APC rs2229992: T>C benign, T>G
    pathogenic). The ClinVar VCF and the DNA files (MyHeritage, src/impute.py) are both on the GRCh37 forward strand,
    so alleles are compared as they are: TC holds no G. Reading the genotype from the other strand would turn TC into
    AG and count a pathogenic G that isn't there."""
    return sum(gt.count(a) for a in alts if len(a) == 1)


def cross_reference(graph, dna_path):
    """Every SNP of the file inside a theme gene, with what ClinVar, the GWAS Catalog and the library say about it.

    Streams the file, so an imputed one with ~28 million calls works too; each finding keeps its call's confidence."""
    traits = json.load(open(TRAITS_PATH, encoding="utf-8"))
    genes_at = in_regions(gene_regions(set(graph["genes"])))
    snps = []
    for rsid, chrom, pos, gt, tier in iter_calls(dna_path, confidence=None):
        if not rsid.startswith("rs") or pos is None:
            continue
        for sym in genes_at(chrom, pos):
            snps.append({"rsid": rsid, "gene": sym, "genotype": gt, "chrom": chrom, "pos": pos, "confidence": tier})
    rsids = {s["rsid"] for s in snps}
    trait_ids = {x for ids in graph["disease_ids"].values() for x in ids}
    clinvar = clinvar_index(rsids)
    known = defaultdict(list)
    gwas = gwas_index({s["rsid"] for s in snps if s["confidence"] in FINDING_TIERS}, trait_ids, known)

    on_theme = re.compile(THEMES[graph["theme"]]["clinvar_terms"], re.I)
    per_gene = defaultdict(lambda: {"n_snps": 0, "by_confidence": defaultdict(int), "findings": []})
    pathogenic = {"measured": 0, "not_excluded": 0, "carried": [], "possible": []}
    for s in snps:
        g = per_gene[s["gene"]]
        gt, tier = s["genotype"], s["confidence"]
        g["by_confidence"][tier] += 1
        if tier in FINDING_TIERS:
            g["n_snps"] += 1
        found = []
        for c in clinvar.get(s["rsid"], []):
            sig = c["significance"].lower()
            if not re.search(r"pathogenic|risk factor|protective|drug response|association", sig) or "conflicting" in sig:
                continue
            is_path = "pathogenic" in sig and "benign" not in sig
            # Pathogenic variants count whatever the disease (carrier status); the rest only when the condition is on the theme
            if not is_path and not on_theme.search(c["condition"]):
                continue
            alts = c["alt"].split(",")
            copies = clinvar_copies(gt, c["ref"], alts)
            if is_path:
                if not copies:
                    # a pathogenic variant the person does not carry is counted, not listed; only confident calls rule it out
                    pathogenic["measured" if tier in CARRIED_TIERS else "not_excluded"] += 1
                    continue
                if tier in CARRIED_TIERS:
                    pathogenic["measured"] += 1
                bucket = pathogenic["carried" if tier in CARRIED_TIERS else "possible"]
                hit = next((x for x in bucket if x["rsid"] == s["rsid"]), None)
                if hit:  # ClinVar lists one variant once per submitted condition
                    if c["condition"] not in hit["condition"]:
                        hit["condition"] += "; " + c["condition"]
                else:
                    bucket.append({"gene": s["gene"], "rsid": s["rsid"], "genotype": gt, "condition": c["condition"],
                                   "copies": copies, "confidence": tier})
                if tier not in CARRIED_TIERS:
                    continue
            elif tier not in FINDING_TIERS:
                continue
            found.append({"source": "ClinVar", "what": f"{c['significance']}: {c['condition']}", "copies": copies,
                          "allele": ",".join(alts)})
        if tier in FINDING_TIERS:
            best = {}
            for a in gwas.get(s["rsid"], []):  # one association per trait: the strongest
                if a["trait"] not in best or a["p"] < best[a["trait"]]["p"]:
                    best[a["trait"]] = a
            for a in best.values():
                risk = a["risk_allele"]
                copies = gt.count(risk) if len(risk) == 1 and risk in "ACGT" else None
                item = {"source": "GWAS", "what": a["trait"], "study": a["study"], "copies": copies, "allele": risk, "p": a["p"],
                        "pubmed": a["pubmed"], "direction": a["direction"], "effect": a["effect"], "kind": a["kind"]}
                if not (len(risk) == 1 and risk in "ACGT"):
                    # The study left the allele out: what other studies of this SNP say, one line per trait
                    seen, related = set(), []
                    for k in known.get(s["rsid"], []):
                        if k["trait"] not in seen and k["trait"] != a["trait"]:
                            seen.add(k["trait"])
                            related.append({**k, "copies": gt.count(k["allele"])})
                    if related:
                        item["related"] = related[:3]
                found.append(item)
        if s["rsid"] in traits and tier in CARRIED_TIERS:
            t = traits[s["rsid"]]
            key = "".join(sorted(gt))
            text = next((v for k, v in t["variants"].items() if "".join(sorted(k)) == key), None)
            found.append({"source": "Library", "what": f"{t.get('trait')}: {text or 'genotype not in library'}", "copies": None})
        if found:
            g["findings"].append({"rsid": s["rsid"], "genotype": gt, "confidence": tier, "items": found})
    by_conf = defaultdict(int)
    for s in snps:
        by_conf[s["confidence"]] += 1
    return {"dna_file": os.path.basename(dna_path), "n_snps_in_theme_genes": sum(by_conf[t] for t in FINDING_TIERS),
            "by_confidence": dict(by_conf), "pathogenic": pathogenic,
            "genes": {k: {**v, "by_confidence": dict(v["by_confidence"])} for k, v in per_gene.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("theme", choices=sorted(THEMES))
    ap.add_argument("--dna", help="DNA file to cross-reference (default: the theme's own person, if it names one)")
    ap.add_argument("--measured-only", action="store_true", help="use the raw file even when an imputed one exists")
    args = ap.parse_args()
    graph = build(args.theme)
    path = os.path.join(os.path.dirname(__file__), f"theme_graph_{args.theme}.json")
    json.dump(graph, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by_mech = {m["id"]: sum(1 for g in graph["genes"].values() if m["id"] in g["mechanisms"]) for m in graph["mechanisms"]}
    print(f"✅ {graph['name']}: {len(graph['genes'])} genes, {len(graph['links'])} links, "
          f"{sum(1 for g in graph['genes'].values() if not g['mechanisms'])} without a GO mechanism | {by_mech} → {path}")
    dna = args.dna or THEMES[args.theme].get("person")
    if dna and not args.measured_only:
        dna = imputed_path(dna)  # the imputed calls when src/impute.py has run for this person
    if dna:
        xref = cross_reference(graph, dna)
        name = person_label(dna)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        out = os.path.join(OUTPUT_DIR, f"theme_{name}_{args.theme}.json")
        json.dump(xref, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n_find = sum(len(g["findings"]) for g in xref["genes"].values())
        print(f"✅ {xref['n_snps_in_theme_genes']} SNPs of the file fall in theme genes; {n_find} have a ClinVar, GWAS or library "
              f"finding, in {sum(1 for g in xref['genes'].values() if g['findings'])} genes → {out}")
        pa = xref["pathogenic"]
        print(f"   calls by confidence: {xref['by_confidence']}\n   pathogenic: {len(pa['carried'])} carried, "
              f"{len(pa['possible'])} possible (weaker imputed calls), {pa['measured']} ruled out or carried confidently, "
              f"{pa['not_excluded']} not detected but not excluded")
