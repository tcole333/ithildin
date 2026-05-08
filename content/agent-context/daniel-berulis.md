# Daniel Berulis
**Stats**: 6 findings, 3 connections, 1 entities
**Dossier**: /dossiers/daniel-berulis

> Berulis is the primary documentary source on the DOGE operation at the NLRB. A career IT professional, he observed, logged, and formally disclosed the sequence of access provisioning, data movement, monitoring suppression, and credential exposure that occurred inside the agency in March 2025. His disclosure serves as the evidentiary foundation for subsequent Congressional investigation and independent forensic analysis of that operation.

## Key Findings
- **[intelligence/high]** Krebs on Security forensic analysis of NLRB DOGE breach: DOGE operatives created accounts (DogeSA_2d5c3e0446f9@nlrb.microsoft.com; 'Whitesox, Chicago M.'; 'Dancehall, Jamaica R.') with tenant-admin privileges exempt from logging. Three external GitHub code libraries downloaded including one designed for 'proxy pool rotation for web scraping and brute forcing.' Microsoft Azure network watcher set to 'off' March 5. April 3-4: NLRB staff instructed to halt US-CERT reporting. April 14: administrative access stripped from IT staff same day NPR published story. NLRB director Lasharn Hamilton claimed no 'official' prior DOGE contact April 16. (2025-03-03) (Finding #6429)
- **[intelligence/confirmed]** On March 11 2025, login attempts from Russian IP address 83.149.30.186 (Primorskiy Krai, Russia's Far East) targeted newly created DOGE accounts at NLRB. Over 20 login attempts, many within 15 minutes of account creation. Attempts used correct username and password. Blocked because NLRB does not allow overseas access. One account: DogeSA_2d5c3e0446f9@nlrb.microsoft.com (2025-03-11) (Finding #6400)
- **[document/confirmed]** Daniel Berulis filed original whistleblower disclosure to Congress and US Office of Special Counsel on April 14 2025 via Whistleblower Aid (attorney: Andrew Bakaj). Primary document: 2025_0414_Berulis-Disclosure-with-Exhibits.s.pdf. Supplemental disclosure added: physical intimidation (threatening note + drone surveillance photos taped to home door), additional forensic data. DOGE visited NLRB on April 16 2025 — the day after NPR reported the disclosure. (2025-04-14) (Finding #6415)
- **[intelligence/confirmed]** DOGE operatives received unrestricted 'tenant owner' level access to NLRB IT systems in March 2025, bypassing standard security controls. Account creation was not logged. MFA was altered. Alerting and monitoring tools were disabled (March 10). (Finding #6396)
- **[intelligence/confirmed]** NLRB whistleblower Daniel Berulis documented 10GB of data (primarily text files) exfiltrated from NLRB NxGen case management system between March 3-5, 2025. Anomalous spike in outbound data traffic observed around 3-4am EST on March 4-5. Data from NxGen included personal info on union members, witness testimony, trade secrets, and proprietary company data. (Finding #6399)
- **[intelligence/confirmed]** While Daniel Berulis was preparing his supplemental disclosure, someone taped a threatening note to his home door, accompanied by drone photographs showing him walking in his neighborhood. Attorney Andrew Bakaj confirmed the note made direct reference to the disclosure Berulis was preparing. This constitutes witness intimidation allegations in the supplemental filing. (Finding #6403)

## Top Connections
- **Andrew Bakaj** [employment/strong]: None
- **Prem Aburvasamy** [employment/strong]: None
- **Lasharn Hamilton** [employment/medium]: None

## Entity Roles
- IT Specialist / Whistleblower at National Labor Relations Board (Federal)

## Open Questions
- The Russian login attempts on March 11 used valid credentials for DOGE accounts created days earlier. How were those credentials obtained? The disclosure records the event but does not resolve whether the credential exposure occurred through the DOGE provisioning process, through the GitHub libraries downloaded to NLRB systems, or through another channel.
- Who within the NLRB chain of command issued the April 3–4 instruction to halt US-CERT incident reporting, and under what authority? Was the instruction relayed from DOGE personnel or initiated by career leadership?
- The 10 GB data transfer from NxGen on March 4–5 has no publicly confirmed destination. Congressional and OIG investigations have not disclosed whether the data was retained, copied, or forwarded after leaving NLRB systems.
- Director Hamilton’s April 16 statement qualified prior DOGE contact as lacking “official” status. What definition of “official” contact does the NLRB apply, and does informal or undocumented access fall outside that definition?
- The threatening note affixed to Berulis’s door referenced the specific disclosure under preparation. Who had knowledge of that disclosure’s contents and timeline before it was filed? Is there a documented chain of custody for that information between Whistleblower Aid and any government or DOGE-connected party?
- Were the three GitHub libraries downloaded to NLRB systems—including one designed for proxy pool rotation for web scraping and brute-forcing—executed on NLRB infrastructure? If so, what systems or external endpoints did they interact with?

## Applicable Models
- regulatory-capture
- private-order
- narrative-shield
- enabler-gradient
