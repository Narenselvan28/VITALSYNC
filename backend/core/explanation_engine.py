"""
VITALSYNC: Deterministic Clinical-Context Explanation Engine
Generates explicit, deterministic, non-diagnostic answers to the 8 Core Questions:
1. WHAT changed?
2. WHETHER the change is genuine or a sensor artifact.
3. WHAT is the most likely contributing context?
4. WHETHER multiple independent signals support the event.
5. WHETHER the condition is transient or persistent.
6. WHETHER the risk is recovering.
7. WHETHER an alert should remain active, escalate, or clear.
8. WHY the system reached its conclusion.

Strict Performance & Medical Constraints:
- Zero LLMs, zero cloud calls, zero external AI APIs.
- Execution latency < 2 ms on Raspberry Pi 4.
- ZERO disease diagnoses (e.g. no "asthma", "heart attack", "stroke", "infection").
- Strictly physiological and contextual descriptions.
"""

from typing import Dict, Any, List, Optional


class ExplanationEngine:
    """
    Deterministic clinical-context reasoning explanation generator.
    Translates raw metrics, ML risk scores, root-cause candidates,
    and state machine status into clean, human-readable answers.
    """

    def generate_clinical_answers(
        self,
        features: Dict[str, Any],
        ml_predictions: Dict[str, Any],
        root_cause_data: Dict[str, Any],
        escalated_eval: Dict[str, Any],
        alert_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synthesizes the deterministic answers for the 8 core clinical questions.
        """
        hr = float(features.get("heart_rate", 72.0))
        spo2 = float(features.get("spo2", 98.0))
        body_temp = float(features.get("body_temperature", 36.7))
        amb_temp = float(features.get("ambient_temperature", 28.0))
        humidity = float(features.get("humidity", 60.0))
        mq45 = float(features.get("mq45", 180.0))

        act_label = features.get("activity_label", "REST")
        is_active = features.get("is_active", False)
        is_rest = features.get("is_rest", True)

        qualities = features.get("sensor_qualities", {})
        ppg_q = float(features.get("ppg_quality", 0.95))
        sensor_conf = float(features.get("overall_sensor_confidence", 1.0))

        baseline_summary = features.get("baseline_summary", {})
        hr_base = baseline_summary.get("hr_baseline", 72.0)
        spo2_base = baseline_summary.get("spo2_baseline", 98.0)
        temp_base = baseline_summary.get("temp_baseline", 36.7)

        hr_dev_pct = round((hr - hr_base) / max(hr_base, 1.0) * 100.0, 1)
        spo2_dev = round(spo2 - spo2_base, 1)

        persistence = escalated_eval.get("persistence_count", 0)
        sm_state = escalated_eval.get("escalated_level", "NORMAL")
        dampened = escalated_eval.get("dampened", False)

        primary_cause = root_cause_data.get("primary", "NORMAL_PHYSIOLOGY")
        confidence = root_cause_data.get("confidence", 0.90)
        is_artifact = root_cause_data.get("is_artifact", False)
        is_recovering = root_cause_data.get("is_recovering", False) or sm_state == "RECOVERING"

        domains = ml_predictions.get("risk_domains", {})
        fall_info = domains.get("fall_event", {})
        is_fall_confirmed = fall_info.get("is_confirmed", False)
        is_fall_candidate = fall_info.get("is_candidate", False)

        # ---------------------------------------------------------------------
        # 1. WHAT CHANGED?
        # ---------------------------------------------------------------------
        changes = []
        if is_fall_confirmed:
            changes.append("Kinetic impact spike detected followed by immediate body tilt and cessation of motion.")
        elif is_fall_candidate:
            changes.append("Kinetic acceleration impact detected, awaiting immobility confirmation.")
        else:
            if abs(hr_dev_pct) >= 15.0:
                direction = "elevated" if hr_dev_pct > 0 else "depressed"
                changes.append(f"Heart rate is {direction} to {int(hr)} BPM ({'+' if hr_dev_pct > 0 else ''}{hr_dev_pct}% vs resting baseline {int(hr_base)} BPM).")
            if spo2 <= 94.0:
                changes.append(f"SpO2 oxygen saturation desaturated to {spo2:.1f}% ({spo2_dev}% vs baseline {spo2_base:.1f}%).")
            if body_temp > 38.0:
                changes.append(f"NTC contact temperature elevated to {body_temp:.1f}°C.")
            elif body_temp < 35.5 and body_temp > 20.0:
                changes.append(f"NTC contact temperature lowered to {body_temp:.1f}°C.")
            if mq45 > 450:
                changes.append(f"MQ-45 air/gas exposure index elevated to {int(mq45)} (nominal < 350).")
            if not changes:
                changes.append(f"All monitored physiological parameters remain aligned with personal baseline (HR {int(hr)} BPM, SpO2 {spo2:.0f}%, Temp {body_temp:.1f}°C).")

        what_changed = " ".join(changes)

        # ---------------------------------------------------------------------
        # 2. WHETHER THE CHANGE IS GENUINE OR A SENSOR ARTIFACT
        # ---------------------------------------------------------------------
        if is_artifact:
            if ppg_q < 0.45 or qualities.get("ppg") in ("WEAK", "INVALID"):
                is_sensor_artifact = True
                genuine_verdict = f"SENSOR ARTIFACT: Low PPG signal quality index ({ppg_q:.2f}). Reading downweighted due to optical motion noise or poor skin coupling."
            elif features.get("is_transient_thermal", False):
                is_sensor_artifact = True
                genuine_verdict = "SENSOR ARTIFACT: Rapid contact temperature transient (>0.8°C/s) without corresponding core physiological change (hot beverage or surface touch)."
            elif not features.get("adxl_available", True):
                is_sensor_artifact = True
                genuine_verdict = "SENSOR ARTIFACT: Accelerometer unavailable or I2C bus error. Fall detection suspended to prevent false alarms."
            else:
                is_sensor_artifact = True
                genuine_verdict = "SENSOR ARTIFACT: Isolated single-sample spike without temporal persistence."
        elif qualities.get("ppg") == "GOOD" or ppg_q >= 0.70:
            is_sensor_artifact = False
            genuine_verdict = f"GENUINE SIGNAL: High optical quality ({ppg_q:.2f}) and valid sensor coupling confirm genuine physiological telemetry."
        else:
            is_sensor_artifact = False
            genuine_verdict = f"BORDERLINE SIGNAL: Signal quality acceptable ({ppg_q:.2f}); confidence slightly attenuated."

        # ---------------------------------------------------------------------
        # 3. WHAT IS THE MOST LIKELY CONTRIBUTING CONTEXT?
        # ---------------------------------------------------------------------
        if is_fall_confirmed or is_fall_candidate:
            contributing_context = f"Sudden gravitational vector reorientation and kinetic impact while in {act_label} state."
        elif primary_cause == "ACTIVITY_RELATED":
            contributing_context = f"Physical exertion ({act_label}). Metabolic cardiovascular demand corresponds directly to observed motion."
        elif primary_cause == "THERMAL_RELATED":
            contributing_context = f"Environmental thermal exposure. Ambient temperature is {amb_temp:.1f}°C (humidity {humidity:.0f}%) placing strain on thermoregulation."
        elif primary_cause == "ENVIRONMENT_RELATED":
            contributing_context = f"Elevated environmental gas/smoke exposure index ({int(mq45)}) detected in the ambient microclimate."
        elif is_rest and (hr > 125 or spo2 < 93):
            contributing_context = f"Sedentary / resting state ({act_label}). Telemetry deviation occurs without physical exertion context."
        elif primary_cause == "SENSOR_ARTIFACT":
            contributing_context = "Mechanical sensor displacement, loose contact, or external thermal disturbance."
        else:
            contributing_context = f"Nominal baseline context under {act_label} activity conditions."

        # ---------------------------------------------------------------------
        # 4. WHETHER MULTIPLE INDEPENDENT SIGNALS SUPPORT THE EVENT
        # ---------------------------------------------------------------------
        independent_signals = []
        if hr > 120 and is_rest:
            independent_signals.append("Resting Tachycardia")
        if spo2 <= 93.0:
            independent_signals.append(f"Desaturation ({spo2:.0f}%)")
        if body_temp > 38.0:
            independent_signals.append(f"Elevated NTC ({body_temp:.1f}°C)")
        if mq45 > 450:
            independent_signals.append(f"Gas Index ({int(mq45)})")
        if is_fall_confirmed:
            independent_signals.append("Impact Spike + Posture Tilt + Inactivity")

        multimodal_count = len(independent_signals)
        if multimodal_count >= 2:
            multimodal_support = True
            multimodal_verdict = f"STRONG MULTI-SIGNAL CONCORDANCE ({multimodal_count} independent channels): " + ", ".join(independent_signals) + "."
        elif multimodal_count == 1:
            multimodal_support = False
            multimodal_verdict = f"ISOLATED SINGLE SIGNAL: Only {independent_signals[0]} is abnormal; other physiological channels remain stable."
        else:
            multimodal_support = False
            multimodal_verdict = "NOMINAL: Zero abnormal signals detected across all physiological and environmental sensors."

        # ---------------------------------------------------------------------
        # 5. WHETHER THE CONDITION IS TRANSIENT OR PERSISTENT
        # ---------------------------------------------------------------------
        if is_artifact or features.get("is_transient_spike", False) or features.get("is_transient_thermal", False):
            temporal_persistence = "TRANSIENT"
            temporal_verdict = "Transient disturbance. Does not satisfy minimum temporal duration thresholds for escalation."
        elif persistence >= 3 or sm_state in ("ELEVATED", "CRITICAL"):
            temporal_persistence = "PERSISTENT"
            temporal_verdict = f"Persistent condition sustained across {persistence} consecutive evaluation epochs."
        elif persistence in (1, 2) or sm_state in ("OBSERVATION", "EARLY_WARNING"):
            temporal_persistence = "OBSERVATION"
            temporal_verdict = f"Early deviation under active observation (duration: {persistence} samples). Awaiting persistence confirmation."
        elif is_recovering:
            temporal_persistence = "RECOVERING"
            temporal_verdict = "Condition is actively de-escalating towards nominal baseline."
        else:
            temporal_persistence = "NORMAL"
            temporal_verdict = "Stable temporal baseline with no significant deviation."

        # ---------------------------------------------------------------------
        # 6. WHETHER THE RISK IS RECOVERING
        # ---------------------------------------------------------------------
        if is_recovering:
            recovery_verdict = "YES: Active physiological recovery detected. Vital telemetry is trending towards personal baseline."
        elif sm_state in ("NORMAL", "OBSERVATION") and persistence == 0:
            recovery_verdict = "STABLE: User is in stable resting equilibrium within normal baseline bounds."
        else:
            recovery_verdict = "NO: Telemetry remains in active deviation state; recovery criteria not yet met."

        # ---------------------------------------------------------------------
        # 7. WHETHER AN ALERT SHOULD REMAIN ACTIVE, ESCALATE, OR CLEAR
        # ---------------------------------------------------------------------
        if sm_state == "CRITICAL":
            alert_verdict = "ESCALATE / ACTIVE: High-risk persistence confirmed. Caretaker notification active."
            alert_recommendation = "ACTIVE_CRITICAL"
        elif sm_state == "ELEVATED":
            alert_verdict = "ACTIVE ELEVATED: Warning state active. Continuous monitoring in progress."
            alert_recommendation = "ACTIVE_ELEVATED"
        elif sm_state == "RECOVERING":
            alert_verdict = "CLEARING: Entering recovery cooldown. Alert will clear once baseline stability persists."
            alert_recommendation = "CLEARING"
        elif sm_state in ("OBSERVATION", "EARLY_WARNING"):
            alert_verdict = "HOLD: Observation state. Maintain local tracking without disturbing caretakers."
            alert_recommendation = "HOLD_OBSERVATION"
        else:
            alert_verdict = "CLEAR: System in nominal state. No active alerts."
            alert_recommendation = "CLEAR"

        # ---------------------------------------------------------------------
        # 8. WHY THE SYSTEM REACHED ITS CONCLUSION
        # ---------------------------------------------------------------------
        reasoning_parts = []
        if primary_cause == "ACTIVITY_RELATED":
            reasoning_parts.append(
                f"Heart rate ({int(hr)} BPM) is elevated above resting baseline ({int(hr_base)} BPM), but ADXL345 motion confirms {act_label} activity while SpO2 is stable ({spo2:.0f}%). Conclusion: physiological cardiovascular response to physical exertion, NOT a medical crisis."
            )
        elif primary_cause == "SENSOR_ARTIFACT":
            reasoning_parts.append(
                f"Telemetry deviation was rejected as a sensor artifact because optical signal quality ({ppg_q:.2f}) or thermal velocity ({features.get('temp_rate_of_change', 0.0):.2f}°C/s) violates physiological plausibility."
            )
        elif primary_cause == "THERMAL_RELATED":
            reasoning_parts.append(
                f"Thermal strain model responded to combined ambient heat ({amb_temp:.1f}°C) and skin temperature ({body_temp:.1f}°C). Physiological compensation is monitored in context of environmental temperature."
            )
        elif primary_cause == "ENVIRONMENT_RELATED":
            reasoning_parts.append(
                f"MQ-45 gas indicator ({int(mq45)}) exceeds nominal baseline, while physiological vitals remain stable. Categorized as environmental advisory, NOT an internal respiratory pathology."
            )
        elif primary_cause == "FALL_EVENT":
            reasoning_parts.append(
                "ADXL345 tri-axial acceleration recorded a high-g impact followed by rapid angle tilt and cessation of arm motion, satisfying the multi-stage fall state machine."
            )
        elif primary_cause == "PHYSIOLOGICAL_ANOMALY":
            reasoning_parts.append(
                f"Persistent vital sign deviation at rest (HR {int(hr)} BPM, SpO2 {spo2:.0f}%) confirmed across sustained temporal window with high optical sensor quality ({ppg_q:.2f})."
            )
        else:
            reasoning_parts.append(
                "All primary vital signs, activity metrics, and environmental indicators track within personal baseline limits."
            )

        reasoning_summary = " ".join(reasoning_parts)

        return {
            "what_changed": what_changed,
            "is_sensor_artifact": is_sensor_artifact,
            "genuine_verdict": genuine_verdict,
            "contributing_context": contributing_context,
            "multimodal_support": multimodal_support,
            "multimodal_verdict": multimodal_verdict,
            "temporal_persistence": temporal_persistence,
            "temporal_verdict": temporal_verdict,
            "is_recovering": is_recovering,
            "recovery_verdict": recovery_verdict,
            "alert_recommendation": alert_recommendation,
            "alert_verdict": alert_verdict,
            "reasoning_summary": reasoning_summary,
            "primary_cause": primary_cause,
            "confidence": confidence,
        }


_explanation_engine = ExplanationEngine()

def get_explanation_engine() -> ExplanationEngine:
    return _explanation_engine
