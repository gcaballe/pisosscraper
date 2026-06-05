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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scraper", choices=list(SCRAPERS))
    parser.add_argument("--db", action="store_true", help="Save results to MariaDB")
    parser.add_argument("--individual", metavar="ID", help="Scrape a single property by ID (idealista only)")
    args = parser.parse_args()

    if args.individual:
        if args.scraper != "idealista":
            parser.error("--individual is only supported for the idealista scraper")
        offer = idealista.scrape_individual(args.individual)
        print(json.dumps(offer, ensure_ascii=False, indent=2))
        return

    offers = SCRAPERS[args.scraper]()
    print(f"Found {len(offers)} houses\n")
    for offer in offers:
        print(f"Name:  {offer['name']}")
        print(f"Price: {offer['price']}")
        if offer.get("rooms"):
            print(f"Rooms: {offer['rooms']}")
        if offer.get("surface"):
            print(f"Surface: {offer['surface']}")
        if offer.get("zone"):
            print(f"Zone:  {offer['zone']}")
        if offer.get("description"):
            print(f"Desc:  {offer['description'][:30]}")
        print(f"URL:   {offer['url']}")
        print()

    if args.db:
        import db
        db.save_scan(args.scraper, offers)


if __name__ == "__main__":
    main()
