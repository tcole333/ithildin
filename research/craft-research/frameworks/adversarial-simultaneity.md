---
name: Adversarial Simultaneity
slug: adversarial-simultaneity
domain: intelligence
source: "Pattern derived from covert action doctrine (Lowenthal 2019) and documented multi-client operations in Epstein corpus; related to Simmel's concept of the tertius gaudens (the 'rejoicing third')"
status: adopted
created: 2026-02-20
grounding_findings: [1385, 1391, 1436, 1388, 1257, 1431, 1450, 892]
related_models: [bridge-tax, intelligence-brokerage, manufactured-dependency]
detection_keywords:
  - ["both sides", "opposing sides", "simultaneously representing", "dual engagement", "conflicting interests"]
  - ["anti-qatar", "pro-qatar", "qatar blockade", "gulf blockade", "playing both sides"]
  - ["co-conspirators", "conflict of interest", "extraordinary conflict", "dual role"]
  - ["brokering legal representation", "client brokering", "representing both"]
  - ["shared intelligence with opposing", "forwarded to", "shared with", "offered to represent"]
  - ["minimize israeli profile", "navigate wash views", "connect opposing parties"]
---

## Definition

Adversarial simultaneity is the deliberate maintenance of active relationships with opposing parties in a conflict, where the operator provides genuine value to each side while exploiting the information asymmetry between them. The operator does not merely "know people on both sides" -- they actively serve, advise, or represent competing interests concurrently, using each relationship to generate leverage with the other.

This pattern is distinct from the Bridge Tax in two ways. First, Bridge Tax describes connecting *disconnected* groups -- groups that don't communicate and may not know of each other. Adversarial simultaneity describes connecting *opposing* groups -- groups that are actively competing, litigating, or at war. The structural dynamics are different: in Bridge Tax, the broker benefits from the *distance* between groups; in adversarial simultaneity, the broker benefits from the *conflict* between them. Second, Bridge Tax is passive -- the broker extracts rent from their position. Adversarial simultaneity is active -- the broker may intensify the conflict because conflict increases the value of their position on both sides.

The canonical instance is Epstein's Gulf operations. The documentary record shows:
- Jun 2017: Epstein offered Ruemmler the opportunity to represent Hamad bin Jassim (HBJ), former PM of Qatar -- the pro-Qatar side.
- Oct 2016: Epstein introduced Ruemmler to Raafat Alsabbagh and Aziza Alahmadi -- Saudi contacts, aligned with the anti-Qatar blockade coalition.
- Mar 2018: Ruemmler was "involved in the WSJ matter" representing Elliott Broidy -- a key figure in the anti-Qatar Nader-Broidy operation.
- Mar 2018: Ruemmler was simultaneously confirmed representing George Nader -- Broidy's co-conspirator in the anti-Qatar scheme, but also a Mueller investigation cooperator.
- Apr 2019: Epstein forwarded the Nader-Broidy-Qatar article *to his Qatari contact Jabor* -- sharing intelligence about the anti-Qatar operation with the target of that operation.

The broker sits at the center of an adversarial system, offering genuine professional services to each side, while the information flowing through them from all sides compounds into comprehensive situational awareness that no single party possesses. The conflict itself becomes the product: as tensions escalate (Qatar blockade, 1MDB investigations, Gulf rivalry), the demand for the broker's services on all sides increases.

For open-source investigators, the detection opportunity is that adversarial simultaneity requires *concurrent* relationships with opposing parties, and these relationships leave traces in introduction emails, legal representation records, scheduling, and forwarded articles. When the same individual or small network appears in the documentary record serving both sides of a known conflict within the same time window, the pattern is triggered.

## Detection Markers

- Same individual or entity providing professional services (legal representation, advisory, introductions) to opposing parties in a documented conflict
- Introduction emails connecting the broker to parties on different sides of a geopolitical, legal, or corporate conflict within overlapping time periods
- Intelligence from one side of a conflict forwarded to the other side through the broker's communications
- Attorney or advisor with documented conflict of interest across adversarial parties (particularly without ethical walls or disclosure)
- Broker offering to represent or introduce counsel to both a plaintiff and defendant, or both an aggressor and target, in the same matter
- Language indicating awareness of the conflict while maintaining both relationships: "minimize Israeli profile" (Barak pitching Carbyne to Qatar), "navigate wash views on intl law and sanctions" (Epstein describing HBJ's legal needs)
- Temporal overlap: documented engagement with Party A and Party B in the same weeks or months when A and B are in active opposition
- Escalation benefit: evidence that the broker's value or fees increased as the conflict between their contacts intensified

## Limitations

- Large law firms and consultancies routinely represent parties with adverse interests, using ethical walls and conflict-checking procedures. The model applies when the adversarial representation is *coordinated through a single broker* who benefits from the conflict, not when institutional firewalls properly separate the representations.
- "Playing both sides" is a common accusation in geopolitics. The model requires documentary evidence of concurrent engagement with opposing parties, not inference from the broker's social connections. Knowing people on both sides of a conflict is not adversarial simultaneity -- actively serving both sides is.
- The model can attribute strategic intent to what may be opportunistic behavior. Not every dual engagement is a deliberate strategy; some may reflect a broker who simply says yes to everyone. Require evidence of information flow between the sides (not just parallel relationships) before classifying as deliberate adversarial simultaneity.
- The Gulf conflict case is unusually well-documented because the Epstein corpus preserves email chains from multiple sides. Most adversarial operations would not leave this kind of paper trail.
