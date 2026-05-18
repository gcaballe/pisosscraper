import argparse
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
    args = parser.parse_args()

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
