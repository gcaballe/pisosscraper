import argparse
import json
import habitaclia
import fotocasa
import idealista
import yaencontre

SCRAPERS = {
    "habitaclia": habitaclia.scrape,
    "fotocasa": fotocasa.scrape,
    "idealista": idealista.scrape,
    "yaencontre": yaencontre.scrape,
}

INDIVIDUAL_SCRAPERS = {
    "idealista": idealista.scrape_individual,
    "yaencontre": yaencontre.scrape_individual,
}


def _print_offers(offers):
    print(json.dumps(offers, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scraper", choices=list(SCRAPERS))
    parser.add_argument("--db", action="store_true", help="Save results to MariaDB")
    parser.add_argument("--individual", metavar="ID", help="Scrape a single property by ID")
    parser.add_argument("--limit", type=int, default=None, metavar="N", help="Stop after N results")
    args = parser.parse_args()

    if args.individual:
        if args.scraper not in INDIVIDUAL_SCRAPERS:
            parser.error(f"--individual is not supported for the {args.scraper} scraper")
        offer = INDIVIDUAL_SCRAPERS[args.scraper](args.individual)
        _print_offers([offer])
        if args.db:
            import db
            db.save_scan(args.scraper, [offer])
        return

    offers = SCRAPERS[args.scraper](limit=args.limit)
    _print_offers(offers)

    if args.db:
        import db
        db.save_scan(args.scraper, offers)


if __name__ == "__main__":
    main()
