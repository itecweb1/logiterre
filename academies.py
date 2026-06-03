# List of academic institutions, universities, and research centers
ACADEMIES = [
    # Universities & Research Centers - Transport & Logistique
    {"short": "TRB_NAS", "name": "Transportation Research Board (TRB) - National Academies of Sciences, Engineering, and Medicine", "country": "United States", "emails": ["trb@nas.edu", "meetings@nas.edu", "webinars@nas.edu", "studies@nas.edu", "annualmeeting@nas.edu", "cooperativehighwayresearch@nas.edu"]},
    {"short": "WMU", "name": "World Maritime University (WMU) - International Maritime Organization (IMO / UN System)", "country": "Sweden", "emails": ["info@wmu.se", "admissions@wmu.se", "communications@wmu.se", "rector@wmu.se", "registry@wmu.se", "research@wmu.se"]},
    {"short": "AFT_IFTIM_AFTRAL", "name": "AFT-IFTIM / AFTRAL (Apprendre et se Former en Transport et Logistique)", "country": "France", "emails": ["international@aftral.com", "info@aftral.com", "partenariats@aftral.com", "direction@aftral.com", "communication@aftral.com", "entreprise@aftral.com"]},
    {"short": "CERTH_HIT", "name": "Centre for Research and Technology Hellas - Hellenic Institute of Transport (CERTH-HIT)", "country": "Greece", "emails": ["hit@certh.gr", "certh@certh.gr", "research@certh.gr", "projects@certh.gr", "partnerships@certh.gr", "info@certh.gr"]},
    {"short": "MIT_CTL", "name": "MIT Center for Transportation & Logistics (MIT CTL)", "country": "United States", "emails": ["ctl-communications@mit.edu", "ctl-info@mit.edu", "execed@mit.edu", "scm-info@mit.edu"]},
    {"short": "TTI", "name": "Texas A&M Transportation Institute (TTI)", "country": "United States", "emails": ["tti-info@tti.tamu.edu", "communications@tti.tamu.edu", "research@tti.tamu.edu", "events@tti.tamu.edu"]},
    {"short": "CTR_Austin", "name": "Center for Transportation Research - University of Texas at Austin (CTR)", "country": "United States", "emails": ["ctr-info@austin.utexas.edu", "ctr@utexas.edu", "research@ctr.utexas.edu", "outreach@ctr.utexas.edu"]},
    {"short": "NUTC", "name": "Northwestern University Transportation Center (NUTC)", "country": "United States", "emails": ["tcinfo@northwestern.edu", "transportation@northwestern.edu", "execed@northwestern.edu"]},
    {"short": "CILT_International", "name": "Chartered Institute of Logistics and Transport International (CILT International)", "country": "United Kingdom", "emails": ["info@ciltinternational.org", "membership@ciltinternational.org", "events@ciltinternational.org", "communications@ciltinternational.org"]},
    {"short": "UCL_PEARL", "name": "UCL PEARL - University College London", "country": "United Kingdom", "emails": ["pearl@ucl.ac.uk", "engineering@ucl.ac.uk", "transport@ucl.ac.uk", "partnerships@ucl.ac.uk"]},
    {"short": "ITS_Leeds", "name": "Institute for Transport Studies - University of Leeds (ITS Leeds)", "country": "United Kingdom", "emails": ["admissions@its.leeds.ac.uk", "info@its.leeds.ac.uk", "research@its.leeds.ac.uk", "business@its.leeds.ac.uk"]},
    {"short": "TU_Delft", "name": "Delft University of Technology - Transport & Planning (TU Delft)", "country": "Netherlands", "emails": ["secretary-tp-citg@tudelft.nl", "citg@tudelft.nl", "transport@tudelft.nl", "internationaloffice@tudelft.nl"]},
    {"short": "Erasmus_MEL", "name": "Erasmus University Rotterdam - Maritime Economics & Logistics (MEL)", "country": "Netherlands", "emails": ["info@meloffice.nl", "mel@ese.eur.nl", "executiveeducation@ese.eur.nl"]},
    {"short": "KLU", "name": "Kühne Logistics University (KLU)", "country": "Germany", "emails": ["info@the-klu.org", "admissions@klu.org", "executiveeducation@klu.org", "corporate@klu.org"]},
    {"short": "Gustave_Eiffel_SPLOTT", "name": "Université Gustave Eiffel - SPLOTT Laboratory", "country": "France", "emails": ["splott@univ-eiffel.fr", "recherche@univ-eiffel.fr", "relations.internationales@univ-eiffel.fr"]},
    {"short": "CRET_LOG", "name": "CRET-LOG - Aix-Marseille Université", "country": "France", "emails": ["cret-log@univ-amu.fr", "contact@cret-log.com", "recherche@univ-amu.fr"]},
    {"short": "LCL_Luxembourg", "name": "Luxembourg Centre for Logistics (LCL)", "country": "Luxembourg", "emails": ["lcl@uni.lu", "logistics@uni.lu", "partnerships@uni.lu", "research@uni.lu"]},
    {"short": "ZLC", "name": "Zaragoza Logistics Center (ZLC)", "country": "Spain", "emails": ["info@zlc.edu.es", "admissions@zlc.edu.es", "executive.education@zlc.edu.es", "research@zlc.edu.es"]},
    {"short": "IESE_CIIL", "name": "IESE Business School - Center for International Industrial Logistics (CIIL)", "country": "Spain", "emails": ["ciil@iese.edu", "info@iese.edu", "executiveeducation@iese.edu", "corporate@iese.edu"]},
    {"short": "CIRRELT", "name": "Interuniversity Research Centre on Enterprise Networks, Logistics and Transportation (CIRRELT)", "country": "Canada", "emails": ["info@cirrelt.ca", "direction@cirrelt.ca", "recherche@cirrelt.ca", "partenariats@cirrelt.ca"]},
    {"short": "TLI_AP_NUS", "name": "The Logistics Institute - Asia Pacific (TLI-AP, NUS)", "country": "Singapore", "emails": ["tliinfo@nus.edu.sg", "tlisg@nus.edu.sg", "execed@nus.edu.sg", "partnerships@nus.edu.sg"]},
    {"short": "BJTU", "name": "Beijing Jiaotong University (BJTU)", "country": "China", "emails": ["bjtubao@bjtu.edu.cn", "international@bjtu.edu.cn", "admissions@bjtu.edu.cn", "research@bjtu.edu.cn"]},
    {"short": "Ningbo_NSCIM", "name": "Ningbo Supply Chain Innovation Institute", "country": "China", "emails": ["info@nscim.edu.cn", "international@nscim.edu.cn", "partnerships@nscim.edu.cn"]},
    {"short": "KMOU_ITLS", "name": "Korea Maritime & Ocean University (KMOU) - ITLS", "country": "South Korea", "emails": ["webmaster@kmou.ac.kr", "international@kmou.ac.kr", "graduate@kmou.ac.kr", "research@kmou.ac.kr"]},
    {"short": "MISI", "name": "Malaysia Institute for Supply Chain Innovation (MISI)", "country": "Malaysia", "emails": ["info@misi.edu.my", "admissions@misi.edu.my", "executiveeducation@misi.edu.my", "corporate@misi.edu.my"]},
    {"short": "ITLS_Sydney", "name": "Institute of Transport and Logistics Studies - University of Sydney (ITLS)", "country": "Australia", "emails": ["business.itlsinfo@sydney.edu.au", "itlsinfo@sydney.edu.au", "research.itls@sydney.edu.au"]},
    {"short": "RMIT", "name": "RMIT University - Global Transport & Logistics Group", "country": "Australia", "emails": ["transport.logistics@rmit.edu.au", "industry@rmit.edu.au", "research@rmit.edu.au"]},
    {"short": "ITLI_AASTMT", "name": "International Transport & Logistics Institute - AASTMT (ITLI)", "country": "Egypt", "emails": ["itli@aast.edu", "info@aast.edu", "international@aast.edu", "logistics@aast.edu"]},
    {"short": "UM6P", "name": "Mohammed VI Polytechnic University (UM6P) - Sustainable Logistics & Territories Chair", "country": "Morocco", "emails": ["contact@um6p.ma", "research@um6p.ma", "international@um6p.ma", "partnerships@um6p.ma"]},

    # International Institutions
    {"short": "ITF_OECD", "name": "International Transport Forum (ITF/OECD)", "country": "France", "emails": ["itf.contact@itf-oecd.org", "events@itf-oecd.org", "outreach@itf-oecd.org"]},
    {"short": "IRU", "name": "International Road Transport Union (IRU)", "country": "Switzerland", "emails": ["iru@iru.org", "communications@iru.org", "events@iru.org", "advocacy@iru.org"]},
    {"short": "IAPH", "name": "International Association of Ports and Harbors (IAPH)", "country": "Japan", "emails": ["info@iaphworldports.org", "communications@iaphworldports.org", "membership@iaphworldports.org"]},
    {"short": "UITP", "name": "UITP - International Association of Public Transport", "country": "Belgium", "emails": ["info@uitp.org", "events@uitp.org", "media@uitp.org"]},
    {"short": "UIC", "name": "UIC - International Union of Railways", "country": "France", "emails": ["mail@uic.org", "freight@uic.org", "communications@uic.org"]},
    {"short": "SFC", "name": "Smart Freight Centre (SFC)", "country": "Netherlands", "emails": ["info@smartfreightcentre.org", "partnerships@smartfreightcentre.org", "communications@smartfreightcentre.org"]},
    {"short": "Maersk_Moller_ZeroCarbon", "name": "Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping", "country": "Denmark", "emails": ["info@zerocarbonshipping.com", "partnerships@zerocarbonshipping.com"]},
    {"short": "Fraunhofer_IML", "name": "Fraunhofer Institute for Material Flow and Logistics (IML)", "country": "Germany", "emails": ["info@iml.fraunhofer.de", "logistics@iml.fraunhofer.de", "presse@iml.fraunhofer.de"]},
    {"short": "DLR", "name": "DLR - German Aerospace Center (Institute of Transport Research)", "country": "Germany", "emails": ["verkehr@dlr.de", "info@dlr.de", "presse@dlr.de"]},
    {"short": "TRL", "name": "Transport Research Laboratory (TRL)", "country": "United Kingdom", "emails": ["enquiries@trl.co.uk", "consulting@trl.co.uk", "innovation@trl.co.uk"]},
    {"short": "ASTAR_IHPC", "name": "A*STAR Institute of High Performance Computing (IHPC)", "country": "Singapore", "emails": ["contact@ihpc.a-star.edu.sg", "partnerships@a-star.edu.sg"]},
    {"short": "NYU_Marron", "name": "NYU Marron Institute - Urban Freight Lab", "country": "United States", "emails": ["marron.institute@nyu.edu", "urbanfreightlab@uw.edu"]},
    {"short": "CSRF", "name": "Centre for Sustainable Road Freight (CSRF)", "country": "United Kingdom", "emails": ["info@csrf.ac.uk", "partnerships@csrf.ac.uk"]},
    {"short": "Chalmers", "name": "Chalmers University of Technology - Shipping & Marine Technology", "country": "Sweden", "emails": ["shipping@chalmers.se", "maritime@chalmers.se"]},
    {"short": "KRRI", "name": "Korea Railroad Research Institute (KRRI)", "country": "South Korea", "emails": ["krri@krri.re.kr", "international@krri.re.kr", "global@krri.re.kr"]},
    {"short": "RTRI", "name": "Railway Technical Research Institute (RTRI)", "country": "Japan", "emails": ["plan@rtri.or.jp", "international@rtri.or.jp"]},
    {"short": "CARS", "name": "China Academy of Railway Sciences (CARS)", "country": "China", "emails": ["cars@rails.cn", "international@rails.cn"]},
    {"short": "Victoria_SupplyChain", "name": "Institute of Supply Chain and Logistics - Victoria University", "country": "Australia", "emails": ["logistics@vu.edu.au", "partnerships@vu.edu.au"]},
    {"short": "Antwerp_PortInnovation", "name": "Port Innovation Lab - Antwerp-Bruges", "country": "Belgium", "emails": ["info@portofantwerpbruges.com", "innovation@portofantwerpbruges.com"]},
    {"short": "SMI_Singapore", "name": "Singapore Maritime Institute (SMI)", "country": "Singapore", "emails": ["info@maritimeinstitute.sg", "research@maritimeinstitute.sg"]},
    {"short": "NLA_Nordic", "name": "Nordic Logistics Association (NLA)", "country": "Norway", "emails": ["post@nla.no", "logistics@nla.no"]},
    {"short": "ETH_Zurich_IVT", "name": "ETH Zurich - Institute for Transport Planning and Systems", "country": "Switzerland", "emails": ["info@ivt.baug.ethz.ch", "research@ivt.baug.ethz.ch"]},

    # Other Strategic Institutions
    {"short": "IAME", "name": "International Association of Maritime Economists (IAME)", "country": "Global / International", "emails": ["info@iame.info", "secretariat@iame.info"]},
    {"short": "PIANC", "name": "PIANC - World Association for Waterborne Transport Infrastructure", "country": "Belgium", "emails": ["info@pianc.org", "secretary.general@pianc.org"]},
    {"short": "UNECE_ITC", "name": "Inland Transport Committee (UNECE)", "country": "Switzerland", "emails": ["inland.transport@un.org", "unece@un.org"]},
    {"short": "WAPPP", "name": "World Association of PPP Units & Professionals (WAPPP)", "country": "Switzerland", "emails": ["secretariat@wapp.network", "events@wapp.network"]},
    {"short": "IHHA", "name": "International Heavy Haul Association (IHHA)", "country": "Global / International", "emails": ["contact@ihha.net"]},
    {"short": "GCMD", "name": "Global Centre for Maritime Decarbonisation (GCMD)", "country": "Singapore", "emails": ["info@gcformd.org", "partnerships@gcformd.org"]},
    {"short": "ERTICO", "name": "ERTICO - ITS Europe", "country": "Belgium", "emails": ["info@mail.ertico.com", "events@mail.ertico.com"]},
    {"short": "OpenLogistics_Found", "name": "Open Logistics Foundation", "country": "Germany", "emails": ["info@openlogisticsfoundation.org", "community@openlogisticsfoundation.org"]},
    {"short": "ALICE", "name": "ALICE - Alliance for Logistics Innovation through Collaboration in Europe", "country": "Belgium", "emails": ["info@etp-alice.eu", "secretariat@etp-alice.eu"]},
    {"short": "IMB_Maglev", "name": "International Maglev Board (IMB)", "country": "Switzerland", "emails": ["office@maglevboard.net"]},
    {"short": "ERRAC", "name": "European Rail Research Advisory Council (ERRAC)", "country": "Belgium", "emails": ["info@errac.org", "secretariat@errac.org"]},
    {"short": "Shift2Rail", "name": "Shift2Rail / Europe's Rail Joint Undertaking", "country": "Belgium", "emails": ["info@rail-research.europa.eu"]},
    {"short": "AAPA", "name": "American Association of Port Authorities (AAPA)", "country": "United States", "emails": ["info@aapa-ports.org", "membership@aapa-ports.org"]},
    {"short": "CAR_Automotive", "name": "Center for Automotive Research (CAR)", "country": "United States", "emails": ["info@cargroup.org", "communications@cargroup.org"]},
    {"short": "MPA_Academy", "name": "Maritime and Port Authority of Singapore Academy (MPA Academy)", "country": "Singapore", "emails": ["mpa_academy@mpa.gov.sg", "academy@mpa.gov.sg"]},
    {"short": "ITS_America", "name": "Intelligent Transportation Society of America (ITS America)", "country": "United States", "emails": ["info@itsa.org", "events@itsa.org"]},
    {"short": "JIFFA_Academy", "name": "Japan International Freight Forwarders Association (JIFFA)", "country": "Japan", "emails": ["soumu@jiffa.or.jp", "jiffa@jiffa.or.jp"]},
    {"short": "CIS_Shipbrokers", "name": "Chartered Institute of Shipbrokers (CIS)", "country": "United Kingdom", "emails": ["membership@cis.org.uk", "education@cis.org.uk"]},
    {"short": "PortXL_Rotterdam", "name": "Port of Rotterdam Authority - PortXL Innovation Hub", "country": "Netherlands", "emails": ["info@portxl.org", "innovation@portofrotterdam.com"]},
    {"short": "Dubai_Future", "name": "Dubai Future Foundation - Dubai Sandbox / Mobility Programs", "country": "United Arab Emirates", "emails": ["info@dubaifuture.ae"]},
]

# Deduplicate by short name (keep first occurrence)
_seen = set()
_dedup = []
for org in ACADEMIES:
    if org["short"] not in _seen:
        _seen.add(org["short"])
        _dedup.append(org)
ACADEMIES = _dedup

if __name__ == "__main__":
    print(f"Total academic institutions: {len(ACADEMIES)}")
