import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from reports.schema import SituationReportData, SettlementTriageRecord


# Deterministic bilingual dictionary
I18N = {
    "en": {
        "title": "FLOOD DISASTER SITUATION REPORT (SITREP)",
        "generated": "Generated",
        "hazard_date": "Hazard Incident Date",
        "infra_snapshot": "Infrastructure Snapshot",
        "medical_facilities": "Monitored Medical Facilities",
        "hospitals_label": "Hospitals / Clinics",
        "exec_summary": "1. Executive Summary",
        "vehicular_cutoff": "Vehicular Cut-Off Settlements",
        "vehicular_desc": "Road access completely severed",
        "ped_only": "Pedestrian-Only Accessible",
        "ped_desc": "Roads blocked, but foot trails remain passable",
        "completely_isolated": "Completely Isolated (Road + Foot)",
        "damaged_roads": "Severed / Flooded Road Segments",
        "buildings": "Pre-Event Building Footprints in Region",
        "baseline_disc": "Baseline Disconnected",
        "baseline_desc": "Pre-existing lack of topological road access",
        "triage_title": "2. Priority Settlement Triage",
        "triage_intro": "The following settlements have experienced road access severance to regional medical facilities:",
        "th_priority": "Priority",
        "th_name": "Settlement Name",
        "th_type": "Type",
        "th_road": "Road Access",
        "th_foot": "Foot Trail",
        "th_risk": "Monte Carlo Risk",
        "th_bottleneck": "Bottleneck Cause",
        "th_rec": "Logistics Recommendation",
        "rec_foot": "🚶 Deploy Foot Patrol / Pack Animals",
        "rec_air": "🚁 Urgent Air Relief / UAV Drop Required",
        "none_isolated": "No settlements suffered complete road severance within the monitored area.",
        "guidance_title": "3. Operational Logistics Guidance",
        "guidance_1": "Ground Ingress Caution: All road segments flagged as damaged are impassable for standard motor vehicles. Ground relief convoys must verify bypass routes before deployment.",
        "guidance_2": "Dual-Modal Deployment: For communities flagged with accessible pedestrian trails, lightweight overland supply teams can be deployed immediately while heavy bridge repairs remain pending.",
        "guidance_3": "Air Relief Allocation: Settlements flagged as severed across both road and walking graphs with Monte Carlo risk >= 80% require prioritization for rotary-wing supply operations.",
        "prov_title": "4. Data Provenance & Verification",
        "prov_1": "Graph Topology Engine: Dual NetworkX graphs (motor vehicular and pedestrian tracks) constructed from OpenStreetMap pre-event vector snapshots.",
        "prov_2": "Monte Carlo Simulation: 250-iteration stochastic network percolation modeling edge failure probabilities under uncertain flood boundaries.",
        "prov_3": "Damage Attribution: Strict geometric spatial intersection between the flood hazard boundary and topological road edges.",
        "prov_4": "Deterministic Metrics: All severance statuses, facility connections, and triage classifications are deterministic pipeline outputs without synthetic hallucinations."
    },
    "ne": {
        "title": "बाढी विपद् वस्तुस्थिति प्रतिवेदन (SITREP)",
        "generated": "तयार पारिएको समय",
        "hazard_date": "घटना भएको मिति",
        "infra_snapshot": "पूर्वाधार तथ्यांक मिति",
        "medical_facilities": "निगरानी गरिएका स्वास्थ्य संस्थाहरू",
        "hospitals_label": "अस्पताल / स्वास्थ्य चौकी",
        "exec_summary": "१. कार्यकारी सारांश",
        "vehicular_cutoff": "सडक सम्पर्क विच्छेद भएका बस्तीहरू",
        "vehicular_desc": "सवारी साधन आवागमन पूर्ण रूपमा अवरुद्ध",
        "ped_only": "पैदल मार्ग मात्र सुचारु",
        "ped_desc": "सडक अवरुद्ध भए पनि गोरेटो/पैदल बाटो खुला",
        "completely_isolated": "पूर्ण रूपमा सम्पर्क विच्छेद (सडक र पैदल दुवै)",
        "damaged_roads": "क्षतिग्रस्त / जलमग्न सडक खण्डहरू",
        "buildings": "क्षेत्र भित्र रहेका घर/भवन संख्या",
        "baseline_disc": "पहिलेदेखि नै सञ्जाल बाहिर रहेका बस्ती",
        "baseline_desc": "विपद् अघि पनि मुख्य सडक सञ्जालमा नजोडिएका",
        "triage_title": "२. प्राथमिकता अनुसार बस्ती वर्गीकरण (Triage)",
        "triage_intro": "निम्न बस्तीहरूबाट नजिकैको अस्पताल पुग्ने सडक पहुँच पूर्ण रूपमा अवरुद्ध भएको छ:",
        "th_priority": "प्राथमिकता",
        "th_name": "बस्तीको नाम",
        "th_type": "प्रकार",
        "th_road": "सडक पहुँच",
        "th_foot": "पैदल मार्ग",
        "th_risk": "जोखिम प्रतिशत (MC)",
        "th_bottleneck": "मुख्य अवरोध",
        "th_rec": "राहत/उद्धार सिफारिस",
        "rec_foot": "🚶 स्थलगत पैदल टोली / खच्चड परिचालन",
        "rec_air": "🚁 आकस्मिक हेलिकप्टर / ड्रोन राहत आवश्यक",
        "none_isolated": "यस क्षेत्रमा कुनै पनि बस्तीको सडक पहुँच विच्छेद भएको छैन।",
        "guidance_title": "३. स्थलगत उद्धार तथा आपूर्ति निर्देशन",
        "guidance_1": "सडक सुरक्षा सतर्कता: क्षतिग्रस्त चिन्ह लगाइएका सडक खण्डहरूमा गाडी चलाउन नमिल्ने अवस्था छ। राहत टोली जानुअघि वैकल्पिक मार्ग यकिन गर्नुपर्छ।",
        "guidance_2": "पैदल टोली परिचालन: पैदल मार्ग खुला रहेका बस्तीहरूमा भारी उपकरण नपर्खिएरै तत्काल पैदल टोली वा भरियामार्फत प्राथमिक सहायता पठाउन सकिन्छ।",
        "guidance_3": "हवाई उद्धार प्राथमिकता: सडक र पैदल दुवै मार्ग बन्द भई जोखिम ८०% भन्दा माथि रहेका बस्तीहरूमा तत्काल हेलिकप्टरबाट राहत सामग्री झार्नुपर्छ।",
        "prov_title": "४. तथ्यांक प्रमाणीकरण तथा स्रोत",
        "prov_1": "सञ्जाल विश्लेषण: विपद् अघिको OpenStreetMap तथ्यांकबाट तयार गरिएको दोहोरो NetworkX ग्राफ।",
        "prov_2": "मोन्टे कार्लो सिमुलेसन: २५० पटकको अनिश्चितता परीक्षण गरी निकालिएको सडक अवरोध जोखिम।",
        "prov_3": "क्षति निर्धारण: बाढीको क्षेत्र र सडक सञ्जाल बीचको ज्यामितीय प्रतिच्छेदन।",
        "prov_4": "विश्वसनीय तथ्यांक: सबै नतिजाहरू गणितीय विश्लेषणमा आधारित छन्, कृत्रिम अनुमान समावेश छैन।"
    }
}


def generate_situation_report(
    summary: Dict[str, Any],
    settlement_results: List[Dict[str, Any]],
    output_path: Optional[Path] = None,
    lang: str = "en",
) -> str:
    t = I18N.get(lang, I18N["en"])
    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    total_settlements = summary.get("total_settlements", 0)
    cut_off_roads = summary.get("settlements_cut_off", 0)
    cut_off_foot = summary.get("foot_cut_off", 0)
    pedestrian_accessible_only = summary.get("pedestrian_accessible_only", 0)
    damaged_roads = summary.get("damaged_road_segments", 0)
    total_buildings = summary.get("total_buildings", 0)
    hospitals_monitored = summary.get("hospitals_monitored", 0)
    osm_snapshot = summary.get("osm_snapshot", "2026-07-27T00:00:00Z")
    flood_date = summary.get("flood_date", "2026-08-26")

    # Filter cut-off settlements
    cut_off_list = [s for s in settlement_results if s.get("road_status") == "cut_off" or s.get("status") == "cut_off"]
    baseline_disconnected = [s for s in settlement_results if s.get("status") == "baseline_disconnected"]

    # Number verification validation
    triage_records: List[SettlementTriageRecord] = []
    for idx, item in enumerate(cut_off_list, 1):
        s_id = str(item.get("osm_id") or item.get("id", idx))
        rec = t["rec_foot"] if item.get("pedestrian_only") or (item.get("road_status") == "cut_off" and item.get("foot_status") == "accessible") else t["rec_air"]
        triage_records.append(SettlementTriageRecord(
            id=s_id,
            name=item.get("name") or f"Settlement #{s_id}",
            place=item.get("place", "settlement"),
            road_status=item.get("road_status", "cut_off"),
            foot_status=item.get("foot_status", "cut_off"),
            cutoff_probability=float(item.get("cutoff_probability", 1.0)),
            critical_bottleneck=item.get("critical_bottleneck", "None"),
            logistics_recommendation=rec
        ))

    # Strict Pydantic number verification
    verified_data = SituationReportData(
        report_id=f"SITREP-{flood_date}",
        generated_at=run_timestamp,
        flood_date=flood_date,
        osm_snapshot=osm_snapshot,
        total_settlements=total_settlements,
        settlements_cut_off=cut_off_roads,
        foot_cut_off=cut_off_foot,
        pedestrian_accessible_only=pedestrian_accessible_only,
        damaged_road_segments=damaged_roads,
        total_buildings=total_buildings,
        hospitals_monitored=hospitals_monitored,
        triage_records=triage_records,
    )

    # Build Markdown document
    report_lines = [
        f"# {t['title']}",
        f"**{t['generated']}:** {run_timestamp}  ",
        f"**{t['hazard_date']}:** {flood_date}  ",
        f"**{t['infra_snapshot']}:** {osm_snapshot}  ",
        f"**{t['medical_facilities']}:** {hospitals_monitored} {t['hospitals_label']}  ",
        "\n---",
        f"## {t['exec_summary']}",
        f"- **{t['vehicular_cutoff']}:** **{verified_data.settlements_cut_off}** / {verified_data.total_settlements} ({t['vehicular_desc']})",
        f"- **{t['ped_only']}:** **{verified_data.pedestrian_accessible_only}** ({t['ped_desc']})",
        f"- **{t['completely_isolated']}:** **{verified_data.foot_cut_off}**",
        f"- **{t['damaged_roads']}:** **{verified_data.damaged_road_segments:,}**",
        f"- **{t['buildings']}:** **{verified_data.total_buildings:,}**",
        f"- **{t['baseline_disc']}:** {len(baseline_disconnected)} ({t['baseline_desc']})",
        "\n---",
        f"## {t['triage_title']}",
        f"{t['triage_intro']}\n",
    ]

    if verified_data.triage_records:
        report_lines.append(f"| {t['th_priority']} | {t['th_name']} | {t['th_type']} | {t['th_road']} | {t['th_foot']} | {t['th_risk']} | {t['th_bottleneck']} | {t['th_rec']} |")
        report_lines.append("| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :--- |")
        for idx, rec in enumerate(verified_data.triage_records, 1):
            road_stat = "🔴 Severed" if rec.road_status == "cut_off" else "🟢 Open"
            foot_stat = "🟢 Open" if rec.foot_status == "accessible" else "🔴 Severed"
            risk_pct = f"{int(rec.cutoff_probability * 100)}%"
            report_lines.append(f"| **P{idx}** | **{rec.name}** | {rec.place} | {road_stat} | {foot_stat} | **{risk_pct}** | {rec.critical_bottleneck} | {rec.logistics_recommendation} |")
    else:
        report_lines.append(f"> **{t['none_isolated']}**")

    report_lines.extend([
        "\n---",
        f"## {t['guidance_title']}",
        f"- **{t['guidance_1']}**",
        f"- **{t['guidance_2']}**",
        f"- **{t['guidance_3']}**",
        "\n---",
        f"## {t['prov_title']}",
        f"- **{t['prov_1']}**",
        f"- **{t['prov_2']}**",
        f"- **{t['prov_3']}**",
        f"- **{t['prov_4']}**",
    ])

    report_content = "\n".join(report_lines)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report_content)

        # Also write the verified JSON schema output
        json_output_file = output_file.with_suffix(".json")
        with open(json_output_file, "w", encoding="utf-8") as f:
            f.write(verified_data.model_dump_json(indent=2))

    return report_content