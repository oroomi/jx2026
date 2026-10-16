"""Test-only: SYNTHETIC rows in the shape of the Estonian e-Business Register basic-data CSV. Never loaded by the app."""
HEADER = "nimi;ariregistri_kood;ettevotja_oiguslik_vorm;ettevotja_staatus;ettevotja_esmakande_kpv;emtak_kood"


def rows(today_minus):
    d = today_minus
    return [
        HEADER,
        f"Fixture Mere OÜ;90000001;OÜ;R;{d(30)};62010",        # name keyword 'mere' -> medium
        f"Fixture Kood OÜ;90000002;OÜ;R;{d(31)};03211",        # EMTAK code in the thesis -> low
        f"Fixture Muu OÜ;90000003;OÜ;R;{d(32)};62010",         # nothing matches -> skipped
        f"Fixture Vana Mere OÜ;90000004;OÜ;R;{d(900)};03211",  # registered long ago -> outside the window
        f"Fixture Mere FIE;90000005;FIE;R;{d(10)};03211",      # sole trader, not a company
        f"Fixture Lõpetatud Mere OÜ;90000006;OÜ;K;{d(10)};03211",  # deleted from the register
        f"Fixture Laev AS;90000007;AS;R;{d(12)};",             # keyword 'laev', no EMTAK code stated
    ]
