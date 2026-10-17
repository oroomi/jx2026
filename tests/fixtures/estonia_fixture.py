"""Test-only (the optional emtak_kood column is NOT in the real basic-data file; it exists here to test the code path): SYNTHETIC rows in the shape of the Estonian e-Business Register basic-data CSV. Never loaded by the app."""
HEADER = "nimi;ariregistri_kood;ettevotja_oiguslik_vorm;ettevotja_staatus;ettevotja_esmakande_kpv;teabesysteemi_link;emtak_kood"


def rows(today_minus):
    ee = lambda n: '.'.join(reversed(today_minus(n).split('-')))  # DD.MM.YYYY like the real file
    return [
        HEADER,
        f"Fixture Mere OÜ;90000001;Osaühing;R;{ee(30)};https://ariregister.rik.ee/est/company/90000001;62010",        # name keyword 'mere' -> medium
        f"Fixture Kood OÜ;90000002;Osaühing;R;{ee(31)};;03210",        # EMTAK code in the thesis -> low
        f"Fixture Muu OÜ;90000003;Osaühing;R;{ee(32)};;62010",         # nothing matches -> skipped
        f"Fixture Vana Mere OÜ;90000004;Osaühing;R;{ee(900)};;03210",  # registered long ago -> outside the window
        f"Fixture Mere FIE;90000005;FIE;R;{ee(10)};;03210",      # sole trader, not a company
        f"Fixture Lõpetatud Mere OÜ;90000006;Osaühing;K;{ee(10)};;03210",  # deleted from the register
        f"Fixture Laev AS;90000007;Aktsiaselts;R;{ee(12)};;",             # keyword 'laev', no EMTAK code stated
    ]
