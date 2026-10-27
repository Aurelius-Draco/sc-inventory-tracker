from sctracker.locations import Locations, system_of


class FakeCat:
    def __init__(self, texts):
        self.loc_names = texts

    def text(self, key):
        low = {k.lower(): v for k, v in self.loc_names.items()}
        return self.loc_names.get(key) or low.get(key.lower())


CAT = FakeCat({
    "Nyx_SocialStation_001": "People's Service Station Alpha",
    "Nyx_Pyro_JPStation": "Pyro Gateway",
    "Stanton_Pyro_JPStation": "Pyro Gateway",
    "Stanton4_Transfer": "Port Tressler",
    "RR_P3": "Orbituary",
    "Stanton2b_Outpost_col_m_drlct_PAF_1-2": "Lamina PAF-II",
    "Stanton4_Shubin_003": "Shubin Mining Facility SM0-18",
    "Stanton2_Orison": "Orison",
})


def loc():
    L = Locations(CAT)
    L.overrides = {}
    L._cache = {}
    return L


def test_direct_and_rules():
    L = loc()
    assert L.name("Stanton2_Orison") == "Orison"
    assert L.name("AsteroidClusterBase_Nyx_Social_Keeger_001") == "People's Service Station Alpha"
    assert L.name("RR_JP_NyxPyro") == "Pyro Gateway (Nyx)"
    assert L.name("RR_JP_StantonPyro") == "Pyro Gateway (Stanton)"
    assert L.name("RR_MIC_LEO") == "Port Tressler"
    assert L.name("RR_P3_LEO") == "Orbituary"
    assert L.name("Outpost_PAF_Stanton2b_Lamina_2") == "Lamina PAF-II"
    assert L.name("Stanton4_Shubin_SM0_18") == "Shubin Mining Facility SM0-18"


def test_unknown_is_tidied():
    assert loc().name("Nyx_TSG_QVExtractionStation_024") == "TSG QV Extraction Station 024"


def test_systems():
    assert system_of("RR_HUR_L1") == "Stanton"
    assert system_of("RR_P5_L2") == "Pyro"
    assert system_of("RR_JP_NyxCastra") == "Nyx"
