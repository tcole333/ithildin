-- Read-only candidate scoring query for the Epstein reporting claims queue.
-- The companion build_claims_queue.py registers the REGEXP function used here.
-- It selects one canonical representative per exact current-content hash.  The
-- stored independence_group is retained for diversity control in Python because
-- most current values are outlet-level (outlet:domain), not story-level lineage.

WITH author_rollup AS (
    SELECT
        ia.item_id,
        group_concat(a.canonical_name, '; ') AS authors
    FROM item_author AS ia
    JOIN author AS a ON a.id = ia.author_id
    GROUP BY ia.item_id
),
corpus AS MATERIALIZED (
    SELECT
        i.id AS item_id,
        i.published_at,
        COALESCE(i.discovery_method, '') AS discovery_method,
        COALESCE(p.name, '') AS publisher,
        COALESCE(p.source_type, 'unknown') AS publisher_type,
        COALESCE(i.language, p.default_language, 'unknown') AS language,
        i.title,
        COALESCE(ar.authors, '') AS authors,
        COALESCE(i.independence_group, 'item:' || i.id) AS independence_group,
        v.content_hash,
        length(trim(v.content_text)) AS content_chars,
        lower(
            COALESCE(i.title, '') || char(10) ||
            COALESCE(i.dek, '') || char(10) ||
            COALESCE(i.abstract, '') || char(10) ||
            COALESCE(v.content_text, '')
        ) AS haystack,
        lower(
            COALESCE(i.title, '') || char(10) ||
            COALESCE(i.dek, '') || char(10) ||
            COALESCE(i.abstract, '')
        ) AS header_text,
        row_number() OVER (
            PARTITION BY v.content_hash
            ORDER BY
                CASE WHEN p.source_type = 'wire_service' THEN 0 ELSE 1 END,
                CASE WHEN i.published_at IS NULL OR trim(i.published_at) = '' THEN 1 ELSE 0 END,
                i.published_at,
                i.id
        ) AS exact_hash_rank,
        count(*) OVER (PARTITION BY v.content_hash) AS exact_duplicate_count
    FROM reporting_item AS i
    JOIN item_version AS v ON v.id = i.current_version_id
    LEFT JOIN publisher AS p ON p.id = i.publisher_id
    LEFT JOIN author_rollup AS ar ON ar.item_id = i.id
    WHERE length(trim(v.content_text)) >= 1200
      AND i.scope_class IN ('direct', 'contextual')
      AND NOT EXISTS (
          SELECT 1 FROM reporting_claim AS c WHERE c.item_id = i.id
      )
),
eligible AS MATERIALIZED (
    SELECT *
    FROM corpus
    WHERE exact_hash_rank = 1
      AND (published_at IS NULL OR substr(published_at, 1, 4) >= '2000')
      AND haystack REGEXP (
          'jeffrey\s+(e[.]?\s+)?epstein|ghislaine\s+maxwell|'
          || 'جيفري.{0,20}إبستين|غيلين.{0,20}ماكسويل|'
          || 'джеффри.{0,20}эпштейн|гисле[йи]н.{0,20}максвел|'
          || 'אפשטיין|爱泼斯坦|愛潑斯坦|エプスタイン|엡스타인'
      )
),
signals AS MATERIALIZED (
    SELECT
        *,
        -- Seven document-grounding families.  Each family contributes at most 1.
        (haystack REGEXP 'court (record|document|filing|paper)|court-filed|docket|case file|documentos? judicial|expediente judicial|dossier judiciaire|pi[eè]ces judiciaires|gerichtsakt|rechtbankstukk|documentos? judicia|atti giudiziar|судебн.{0,20}(документ|материал)')
        + (haystack REGEXP 'released email|emails? (show|reveal|obtained|reviewed)|email records|messages? (show|reveal)|calendar entries|correos? electr[oó]nic|courriels?|e-mails?|электронн.{0,10}письм|رسائل إلكترونية')
        + (haystack REGEXP 'deposition|deposed|testified under oath|sworn testimony|transcript|d[eé]position|testimonio jurado|aussage unter eid|vernehmungsprotokoll|depoimento|depozi|показани|إفادة')
        + (haystack REGEXP 'subpoena|search warrant|affidavit|indictment|criminal complaint|civil complaint|grand jury|citaci[oó]n|assignation|vorladung|durchsuchungsbefehl|intima[cç][aã]o|повестк|обвинительн|مذكرة استدعاء')
        + (haystack REGEXP 'bank records|bank statements|financial records|tax records|tax return|property records|wire transfer records|registros bancarios|registros financieros|documents bancaires|relev[eé]s bancaires|bankunterlagen|kontoausz[uü]g|registros financeiros|estratti conto|банковск.{0,10}(документ|выписк)|سجلات مصرفية')
        + (haystack REGEXP 'records obtained|documents obtained|records reviewed|documents reviewed|newly released (record|document|file)|released (record|document)s? (show|reveal)|according to (court|bank|financial|property|public) records|seg[uú]n (los )?documentos|selon (des|les) documents|aus den unterlagen|volgens (de )?documenten|de acordo com (os )?documentos|согласно документ|وفق.{0,20}(وثائق|سجلات)')
        + (haystack REGEXP 'flight logs?|contact book|address book|visitor logs?|registro de vuelo|carnet d.adresses|flugprotokoll|vluchtlog|di[aá]rio de voo|журнал полет|سجل الرحلات')
        AS document_hits,

        (header_text REGEXP 'exclusive|investigation|investigative|special report|documents? (show|reveal)|records? (show|reveal)|inside |how .* (built|worked|operated)|deep ties|secret|hidden')
        + (haystack REGEXP 'obtained by (the |our )?(associated press|guardian|miami herald|times|post|journal|bbc|cbs|nbc|icij|propublica|bloomberg|reuters)|reviewed by (the |our )?(associated press|guardian|miami herald|times|post|journal|bbc|cbs|nbc|icij|propublica|bloomberg|reuters)')
        + (haystack REGEXP 'interviewed (more than |over )?[0-9]+|months[- ]long investigation|year[- ]long investigation|first reported by|reporting for this (story|article)')
        AS original_reporting_hits,

        (haystack REGEXP 'jpmorgan|j[.]?p[.]?\s*morgan|deutsche bank|fidelity|southern trust|financial trust|trust company|bank account|banking relationship|suspicious activity report|money laundering|wire transfer|tax advice|tax strateg|u[.]?s[.]? virgin islands|usvi|estate executor|darren indyke|richard kahn') AS topic_banks,
        (haystack REGEXP 'les(lie)? wexner|abigail wexner|leon black|apollo global|dechert|l brands|limited brands|victoria.?s secret|mega group') AS topic_wexner_black,
        (haystack REGEXP 'ghislaine maxwell|robert maxwell|isabel maxwell|christine maxwell|maxwell (trial|conviction|sentence|appeal|prosecution|deposition)') AS topic_maxwell,
        (haystack REGEXP 'donald trump|bill clinton|prince andrew|ehud barak|steve bannon|alexander acosta|alan dershowitz|mossad|cia|intelligence service|israeli intelligence|unit 8200|carbyne|white house|congress|parliament|political (figure|donor|campaign)|gulf state|qatar|saudi|emirati') AS topic_politics_intel,
        (haystack REGEXP 'harvard|massachusetts institute of technology|\bmit\b|scientist|science philanthropy|scientific research|professor|university donation|academic|philanthrop|foundation grant|bill gates|boris nikolic|lawrence summers|evolutionary dynamics|edge foundation') AS topic_science_philanthropy,
        (haystack REGEXP 'little st[.]? james|great st[.]? james|zorro ranch|9 east 71|east 71st|358 el brillo|palm beach mansion|manhattan mansion|townhouse|private island|new mexico ranch|paris apartment|property portfolio|real estate|residence in') AS topic_properties,
        (haystack REGEXP 'darren indyke|richard kahn|lesley groff|sarah kellen|nadia marcinkova|karyna shuliak|christina galbraith|household staff|personal assistant|executive assistant|pilot|butler|recruiter|scheduler|employee|staff member|security guard|estate manager|office operations|co-conspirator') AS topic_staff_operations,
        (haystack REGEXP 'non[- ]prosecution agreement|plea agreement|criminal case|civil lawsuit|class action|prosecution|conviction|sentenced|settlement|victim compensation|survivor|sex trafficking trial') AS topic_legal_accountability
        ,
        (
            (length(haystack) - length(replace(haystack, 'jeffrey epstein', ''))) / 15
          + (length(haystack) - length(replace(haystack, 'ghislaine maxwell', ''))) / 16
        ) AS full_name_mentions
    FROM eligible
),
scored AS MATERIALIZED (
    SELECT
        *,
        CASE
            WHEN content_chars >= 12000 THEN 18
            WHEN content_chars >= 8000 THEN 15
            WHEN content_chars >= 5000 THEN 12
            WHEN content_chars >= 3000 THEN 8
            WHEN content_chars >= 1800 THEN 4
            ELSE 1
        END AS length_score,
        CASE
            WHEN document_hits >= 5 THEN 24
            WHEN document_hits = 4 THEN 20
            WHEN document_hits = 3 THEN 16
            WHEN document_hits = 2 THEN 11
            WHEN document_hits = 1 THEN 6
            ELSE 0
        END AS document_score,
        CASE
            WHEN publisher IN ('Miami Herald', 'Palm Beach Post', 'ICIJ', 'OCCRP', 'ProPublica', 'The Intercept', 'Drop Site News', 'The Smoking Gun') THEN 15
            WHEN publisher IN ('Wall Street Journal', 'Bloomberg', 'Financial Times', 'Washington Post', 'The New Yorker', 'Nature', 'The Guardian', 'Le Monde', 'Der Spiegel', 'Süddeutsche Zeitung', 'Die Zeit', 'NRC', 'Haaretz') THEN 9
            WHEN publisher_type = 'academic' THEN 10
            WHEN publisher_type = 'secondary_quality' THEN 6
            WHEN publisher_type = 'trade_press' THEN 4
            WHEN publisher_type = 'broadcast' THEN 1
            WHEN publisher_type = 'wire_service' THEN -10
            WHEN publisher_type IN ('secondary_compromised', 'secondary_blog') THEN -8
            ELSE -2
        END AS publisher_score,
        CASE
            WHEN published_at IS NULL OR trim(published_at) = '' THEN -3
            WHEN substr(published_at, 1, 4) < '2015' THEN 18
            WHEN substr(published_at, 1, 4) < '2019' THEN 12
            WHEN substr(published_at, 1, 4) = '2019' THEN 6
            WHEN substr(published_at, 1, 4) < '2025' THEN 3
            WHEN substr(published_at, 1, 4) = '2025' THEN -3
            ELSE -8
        END AS era_score,
        CASE
            WHEN published_at IS NULL OR trim(published_at) = '' THEN 'undated'
            WHEN substr(published_at, 1, 4) < '2015' THEN 'pre_2015'
            WHEN substr(published_at, 1, 4) < '2019' THEN '2015_2018'
            WHEN substr(published_at, 1, 4) = '2019' THEN '2019'
            WHEN substr(published_at, 1, 4) < '2025' THEN '2020_2024'
            WHEN substr(published_at, 1, 4) = '2025' THEN '2025'
            ELSE '2026_plus'
        END AS era_bucket,
        CASE
            WHEN content_chars < 2500 AND haystack REGEXP 'enable javascript|cookie policy|sign up for (our|the) newsletter|all rights reserved|advertisement' THEN -5
            ELSE 0
        END AS boilerplate_penalty,
        CASE WHEN lower(authors) REGEXP 'landon thomas' THEN -14 ELSE 0 END AS landon_thomas_penalty,
        CASE WHEN lower(authors) REGEXP 'michael wolff' THEN -10 ELSE 0 END AS michael_wolff_penalty,
        CASE
            WHEN discovery_method IN (
                'import:early_reporting',
                'import:palm_beach_post_archive',
                'file:historical_released_reporting',
                'import:historical_released_reporting'
            ) THEN 6 ELSE 0
        END AS curated_history_score,
        CASE
            WHEN content_chars >= 20000 AND full_name_mentions < 2 THEN -12
            WHEN content_chars >= 12000 AND full_name_mentions < 2 THEN -7
            ELSE 0
        END AS subject_density_penalty,
        CASE
            WHEN NOT (header_text REGEXP 'jeffrey\s+(e[.]?\s+)?epstein|ghislaine\s+maxwell|جيفري.{0,20}إبستين|غيلين.{0,20}ماكسويل|джеффри.{0,20}эпштейн|гисле[йи]н.{0,20}максвел|אפשטיין|爱泼斯坦|愛潑斯坦|エプスタイン|엡스타인') THEN -7
            ELSE 0
        END AS body_only_penalty
    FROM signals
)
SELECT
    item_id,
    published_at,
    discovery_method,
    publisher,
    publisher_type,
    language,
    title,
    authors,
    independence_group,
    content_hash,
    content_chars,
    exact_duplicate_count,
    document_hits,
    original_reporting_hits,
    topic_banks,
    topic_wexner_black,
    topic_maxwell,
    topic_politics_intel,
    topic_science_philanthropy,
    topic_properties,
    topic_staff_operations,
    topic_legal_accountability,
    full_name_mentions,
    era_bucket,
    (
        length_score + document_score + publisher_score + era_score
        + min(original_reporting_hits, 3) * 5
        + topic_banks * 7 + topic_wexner_black * 6
        + topic_maxwell * 4 + topic_politics_intel * 4
        + topic_science_philanthropy * 5 + topic_properties * 4
        + topic_staff_operations * 5 + topic_legal_accountability * 2
        + boilerplate_penalty + landon_thomas_penalty
        + michael_wolff_penalty + curated_history_score
        + subject_density_penalty + body_only_penalty
    ) AS base_score
FROM scored
ORDER BY base_score DESC, document_hits DESC, content_chars DESC, item_id;
