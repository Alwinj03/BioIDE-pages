"""Literature retrieval from Europe PMC, OpenAlex, Crossref and PubMed.

Records are normalised into one shape. Nothing is invented: if a provider is
unreachable the error is surfaced with the exact request that failed, and the
caller shows it rather than substituting content.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from ..config import settings
from ..store import store, tracked_run

UA = "BioIDE/0.1 (computational biology IDE)"
PROVIDERS = {
    "europepmc": "Europe PMC REST — abstracts, open-access full text, citation counts",
    "openalex": "OpenAlex — works index with concepts, open-access status and venues",
    "crossref": "Crossref — DOI registration metadata",
    "pubmed": "NCBI PubMed E-utilities — biomedical index with MeSH terms",
}
ARTICLE_TYPES = ["journal-article", "review", "preprint", "book-chapter", "conference-paper"]


def _headers() -> dict:
    h = {"User-Agent": UA, "Accept": "application/json"}
    if settings.contact_email:
        h["User-Agent"] = f"{UA} mailto:{settings.contact_email}"
    return h


def _norm(doi: str | None) -> str | None:
    if not doi:
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip()).lower() or None


def _record(**kw: Any) -> dict:
    r = {"source": None, "id": None, "doi": None, "pmid": None, "pmcid": None, "title": None,
         "authors": [], "year": None, "journal": None, "abstract": None, "article_type": None,
         "citations": None, "is_open_access": None, "url": None, "full_text_url": None, "concepts": []}
    r.update(kw)
    r["doi"] = _norm(r["doi"])
    if not r["url"]:
        if r["doi"]:
            r["url"] = f"https://doi.org/{r['doi']}"
        elif r["pmid"]:
            r["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/"
    return r


# ------------------------------------------------------------- providers

async def _europepmc(client: httpx.AsyncClient, query: str, limit: int, year_min: int | None, year_max: int | None,
                     open_access: bool, article_type: str | None) -> list[dict]:
    q = [query]
    if year_min or year_max:
        q.append(f"PUB_YEAR:[{year_min or 1800} TO {year_max or 2100}]")
    if open_access:
        q.append("OPEN_ACCESS:y")
    if article_type == "review":
        q.append("PUB_TYPE:review")
    elif article_type == "preprint":
        q.append("SRC:PPR")
    params = {"query": " AND ".join(q), "format": "json", "pageSize": min(limit, 100),
              "resultType": "core", "sort": "CITED_BY desc"}
    r = await client.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params=params)
    r.raise_for_status()
    out = []
    for it in r.json().get("resultList", {}).get("result", []):
        ft = None
        for u in (it.get("fullTextUrlList", {}) or {}).get("fullTextUrl", []) or []:
            if u.get("availability") in ("Open access", "Free"):
                ft = u.get("url")
                break
        if not ft and it.get("pmcid"):
            ft = f"https://europepmc.org/article/PMC/{it['pmcid']}"
        out.append(_record(
            source="europepmc", id=f"europepmc:{it.get('id')}", doi=it.get("doi"), pmid=it.get("pmid"),
            pmcid=it.get("pmcid"), title=it.get("title"),
            authors=[a.strip() for a in (it.get("authorString") or "").split(",") if a.strip()][:20],
            year=int(it["pubYear"]) if str(it.get("pubYear", "")).isdigit() else None,
            journal=(it.get("journalInfo") or {}).get("journal", {}).get("title") or it.get("bookOrReportDetails", {}).get("publisher"),
            abstract=it.get("abstractText"), article_type=(it.get("pubTypeList", {}) or {}).get("pubType", [None])[0],
            citations=it.get("citedByCount"), is_open_access=it.get("isOpenAccess") == "Y",
            full_text_url=ft,
        ))
    return out


async def _openalex(client: httpx.AsyncClient, query: str, limit: int, year_min: int | None, year_max: int | None,
                    open_access: bool, article_type: str | None) -> list[dict]:
    filters = []
    if year_min:
        filters.append(f"from_publication_date:{year_min}-01-01")
    if year_max:
        filters.append(f"to_publication_date:{year_max}-12-31")
    if open_access:
        filters.append("is_oa:true")
    if article_type:
        filters.append(f"type:{article_type}")
    params = {"search": query, "per-page": min(limit, 100), "sort": "cited_by_count:desc"}
    if filters:
        params["filter"] = ",".join(filters)
    if settings.contact_email:
        params["mailto"] = settings.contact_email
    r = await client.get("https://api.openalex.org/works", params=params)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []):
        inv = w.get("abstract_inverted_index")
        abstract = None
        if inv:
            pos: dict[int, str] = {}
            for word, idxs in inv.items():
                for i in idxs:
                    pos[i] = word
            abstract = " ".join(pos[k] for k in sorted(pos))
        loc = w.get("primary_location") or {}
        out.append(_record(
            source="openalex", id=w.get("id"), doi=w.get("doi"), title=w.get("title"),
            pmid=(w.get("ids") or {}).get("pmid", "").rsplit("/", 1)[-1] or None,
            authors=[a["author"]["display_name"] for a in (w.get("authorships") or [])[:20]],
            year=w.get("publication_year"), journal=(loc.get("source") or {}).get("display_name"),
            abstract=abstract, article_type=w.get("type"), citations=w.get("cited_by_count"),
            is_open_access=(w.get("open_access") or {}).get("is_oa"),
            full_text_url=(w.get("best_oa_location") or {}).get("pdf_url") or (w.get("open_access") or {}).get("oa_url"),
            concepts=[c["display_name"] for c in (w.get("concepts") or [])[:8]],
        ))
    return out


async def _crossref(client: httpx.AsyncClient, query: str, limit: int, year_min: int | None, year_max: int | None,
                    open_access: bool, article_type: str | None) -> list[dict]:
    params: dict[str, Any] = {"query.bibliographic": query, "rows": min(limit, 100), "sort": "is-referenced-by-count", "order": "desc"}
    f = []
    if year_min:
        f.append(f"from-pub-date:{year_min}-01-01")
    if year_max:
        f.append(f"until-pub-date:{year_max}-12-31")
    if article_type:
        f.append(f"type:{article_type}")
    if f:
        params["filter"] = ",".join(f)
    if settings.contact_email:
        params["mailto"] = settings.contact_email
    r = await client.get("https://api.crossref.org/works", params=params)
    r.raise_for_status()
    out = []
    for it in r.json().get("message", {}).get("items", []):
        parts = (it.get("issued") or {}).get("date-parts") or [[None]]
        out.append(_record(
            source="crossref", id=f"crossref:{it.get('DOI')}", doi=it.get("DOI"),
            title=(it.get("title") or [None])[0],
            authors=[f"{a.get('given','')} {a.get('family','')}".strip() for a in (it.get("author") or [])[:20]],
            year=parts[0][0], journal=(it.get("container-title") or [None])[0],
            abstract=re.sub(r"<[^>]+>", "", it["abstract"]) if it.get("abstract") else None,
            article_type=it.get("type"), citations=it.get("is-referenced-by-count"),
        ))
    return out


async def _pubmed(client: httpx.AsyncClient, query: str, limit: int, year_min: int | None, year_max: int | None,
                  open_access: bool, article_type: str | None) -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    common: dict[str, Any] = {"db": "pubmed", "tool": "BioIDE"}
    if settings.contact_email:
        common["email"] = settings.contact_email
    if settings.ncbi_api_key:
        common["api_key"] = settings.ncbi_api_key
    term = query
    if year_min or year_max:
        term += f" AND {year_min or 1800}:{year_max or 2100}[dp]"
    if article_type == "review":
        term += " AND review[pt]"
    s = await client.get(f"{base}/esearch.fcgi", params=common | {"term": term, "retmax": min(limit, 100), "retmode": "json", "sort": "relevance"})
    s.raise_for_status()
    ids = s.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    f = await client.get(f"{base}/efetch.fcgi", params=common | {"id": ",".join(ids), "retmode": "xml"})
    f.raise_for_status()
    root = ET.fromstring(f.text)
    out = []
    for art in root.findall(".//PubmedArticle"):
        def txt(p: str) -> str | None:
            el = art.find(p)
            return "".join(el.itertext()).strip() if el is not None else None
        abst = " ".join("".join(e.itertext()).strip() for e in art.findall(".//Abstract/AbstractText")) or None
        yr = txt(".//JournalIssue/PubDate/Year") or (txt(".//JournalIssue/PubDate/MedlineDate") or "")[:4]
        doi = None
        for aid in art.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text
        authors = []
        for a in art.findall(".//Author")[:20]:
            ln, fn = a.findtext("LastName"), a.findtext("ForeName")
            if ln:
                authors.append(f"{fn or ''} {ln}".strip())
        out.append(_record(
            source="pubmed", id=f"pubmed:{txt('.//PMID')}", pmid=txt(".//PMID"), doi=doi,
            title=txt(".//ArticleTitle"), authors=authors,
            year=int(yr) if str(yr).isdigit() else None, journal=txt(".//Journal/Title"),
            abstract=abst, article_type=txt(".//PublicationTypeList/PublicationType"),
            concepts=[m.findtext("DescriptorName") for m in art.findall(".//MeshHeading")][:8],
        ))
    return out


_FETCH = {"europepmc": _europepmc, "openalex": _openalex, "crossref": _crossref, "pubmed": _pubmed}


def _dedupe(records: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    order: list[str] = []
    for r in records:
        key = r["doi"] or (f"pmid:{r['pmid']}" if r["pmid"] else None) or re.sub(r"\W+", "", (r["title"] or "").lower())[:70]
        if not key:
            continue
        if key in by_key:
            cur = by_key[key]
            cur["found_in"] = sorted(set(cur.get("found_in", [cur["source"]]) + [r["source"]]))
            for field in ("abstract", "full_text_url", "pmcid", "pmid", "doi", "journal", "year", "article_type"):
                if not cur.get(field) and r.get(field):
                    cur[field] = r[field]
            if (r.get("citations") or 0) > (cur.get("citations") or 0):
                cur["citations"] = r["citations"]
            if r.get("is_open_access"):
                cur["is_open_access"] = True
            cur["concepts"] = sorted(set((cur.get("concepts") or []) + (r.get("concepts") or [])))[:10]
        else:
            r["found_in"] = [r["source"]]
            by_key[key] = r
            order.append(key)
    return [by_key[k] for k in order]


async def search(query: str, providers: list[str] | None = None, limit: int = 20, year_min: int | None = None,
                 year_max: int | None = None, open_access: bool = False, article_type: str | None = None,
                 project_id: str | None = None) -> dict:
    providers = [p for p in (providers or ["europepmc", "openalex"]) if p in _FETCH]
    if not providers:
        raise ValueError(f"No valid provider. Choose from {list(_FETCH)}")
    params = {"query": query, "providers": providers, "limit": limit, "year_min": year_min,
              "year_max": year_max, "open_access": open_access, "article_type": article_type}
    with tracked_run("literature_search", "+".join(providers), "rest-api", params, project_id=project_id) as run:
        errors: dict[str, str] = {}
        results: list[dict] = []
        async with httpx.AsyncClient(timeout=45, headers=_headers(), follow_redirects=True) as client:
            tasks = [_FETCH[p](client, query, limit, year_min, year_max, open_access, article_type) for p in providers]
            for p, res in zip(providers, await asyncio.gather(*tasks, return_exceptions=True)):
                if isinstance(res, Exception):
                    errors[p] = f"{type(res).__name__}: {res}"
                else:
                    results.extend(res)
        merged = _dedupe(results)
        merged.sort(key=lambda r: (-(r.get("citations") or 0), -(r.get("year") or 0)))
        run.summary = {"returned": len(merged), "providers_ok": [p for p in providers if p not in errors], "errors": errors}
        if errors and not merged:
            raise RuntimeError("All literature providers failed: " + "; ".join(f"{k}: {v}" for k, v in errors.items()))
    return {"query": query, "providers_queried": providers, "provider_errors": errors,
            "count": len(merged), "results": merged[:limit], "provenance": run.provenance()}


async def fetch_open_access_text(pmcid: str) -> dict:
    """Retrieve open-access full text from Europe PMC. Only works for OA records."""
    pid = re.sub(r"[^A-Za-z0-9]", "", pmcid).upper()
    if not pid.startswith("PMC"):
        raise ValueError("Expected a PMC identifier, e.g. PMC3539452")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pid}/fullTextXML"
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": UA}, follow_redirects=True) as client:
        r = await client.get(url)
        if r.status_code == 404:
            raise ValueError(f"{pid} has no open-access full text in Europe PMC. Only the abstract is available; "
                             "use the publisher link for the rest.")
        r.raise_for_status()
    root = ET.fromstring(r.text)
    sections = []
    for sec in root.findall(".//body//sec"):
        title = sec.findtext("title") or ""
        body = " ".join(" ".join(p.itertext()).strip() for p in sec.findall("./p"))
        if body:
            sections.append({"title": title, "text": body})
    return {"pmcid": pid, "source_url": url, "sections": sections,
            "n_references": len(root.findall(".//ref")),
            "license": root.findtext(".//license-p") or root.findtext(".//permissions/license/license-p")}


def collection_to_bibtex(papers: list[dict]) -> str:
    out = []
    for p in papers:
        key = (p.get("authors") or ["anon"])[0].split()[-1].lower() + str(p.get("year") or "")
        key = re.sub(r"\W", "", key) or "ref"
        fields = {"title": p.get("title"), "journal": p.get("journal"), "year": p.get("year"),
                  "doi": p.get("doi"), "author": " and ".join(p.get("authors") or [])}
        body = ",\n  ".join(f"{k} = {{{v}}}" for k, v in fields.items() if v)
        out.append(f"@article{{{key},\n  {body}\n}}")
    return "\n\n".join(out)


def save_to_project(project_id: str, record: dict) -> None:
    store.save_paper(project_id, record)
