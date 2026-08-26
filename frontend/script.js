// ===========================================================
// ARGUS — frontend logic
// Connects the frontend to the FastAPI /predict endpoint.
// ===========================================================


// -----------------------------------------------------------
// API
// -----------------------------------------------------------

// FastAPI backend deployed on Vercel
const API_BASE_URL = "https://credit-card-fraud-detection-3pkftltmm-aniha-trivedi.vercel.app";

const API_URL = `${API_BASE_URL}/predict`;

// -----------------------------------------------------------
// DOM elements
// -----------------------------------------------------------

const form = document.getElementById("txn-form");
const submitBtn = document.getElementById("submit-btn");
const formError = document.getElementById("form-error");

const assessmentPanel = document.getElementById("assessment-panel");
const scanline = document.getElementById("scanline");

const gaugeArc = document.getElementById("gauge-arc");
const gaugePercent = document.getElementById("gauge-percent");
const gaugeVerdict = document.getElementById("gauge-verdict");

const metaCardStatus = document.getElementById("meta-card-status");
const metaVelocity = document.getElementById("meta-velocity");
const metaTime = document.getElementById("meta-time");

const modeNote = document.getElementById("mode-note");

const ledgerList = document.getElementById("ledger-list");
const ledgerEmpty = document.getElementById("ledger-empty");
const ledgerCount = document.getElementById("ledger-count");

const historyList = document.getElementById("history-list");
const historyEmpty = document.getElementById("history-empty");
const historyCount = document.getElementById("history-count");

const riskAnalysis = document.getElementById("risk-analysis");
const riskFactorsList = document.getElementById("risk-factors-list");
const riskRecommendationText =
    document.getElementById("risk-recommendation-text");

const clockEl = document.getElementById("clock");

const trustSlider = document.getElementById("device_trust_score");
const trustOut = document.getElementById("device_trust_score_out");


// -----------------------------------------------------------
// Constants
// -----------------------------------------------------------

const GAUGE_CIRCUMFERENCE = 251.33;

let sessionChecks = 0;


// -----------------------------------------------------------
// Live clock
// -----------------------------------------------------------

function tickClock() {

    const now = new Date();

    clockEl.textContent =
        now.toLocaleTimeString("en-IN", {
            hour12: false
        });
}

tickClock();

setInterval(tickClock, 1000);


// -----------------------------------------------------------
// Yes / No pill toggles
// -----------------------------------------------------------

document.querySelectorAll(".pill-group").forEach((group) => {

    const pills = group.querySelectorAll(".pill");

    pills.forEach((pill) => {

        pill.addEventListener("click", () => {

            pills.forEach((p) => {
                p.setAttribute("aria-pressed", "false");
            });

            pill.setAttribute("aria-pressed", "true");
        });

    });

});


// -----------------------------------------------------------
// Get selected Yes / No value
// -----------------------------------------------------------

function getPillValue(name) {

    const group =
        document.querySelector(
            `.pill-group[data-name="${name}"]`
        );

    const active =
        group.querySelector(
            '.pill[aria-pressed="true"]'
        );

    return Number(active.dataset.value);
}


// -----------------------------------------------------------
// Device trust slider
// -----------------------------------------------------------

trustSlider.addEventListener("input", () => {

    trustOut.textContent =
        Number(trustSlider.value).toFixed(2);

});


// -----------------------------------------------------------
// Gauge
// -----------------------------------------------------------

function setGauge(percent, status) {

    const clamped =
        Math.max(0, Math.min(100, percent));

    const offset =
        GAUGE_CIRCUMFERENCE -
        (clamped / 100) * GAUGE_CIRCUMFERENCE;

    gaugeArc.style.strokeDashoffset = offset;


    // Use the backend's actual prediction status
    // as the source of truth.

    let state;
    let color;

    if (status === "Fraud") {

        state = "danger";
        color = "var(--danger)";

    } else if (clamped >= 30) {

        state = "warn";
        color = "var(--warn)";

    } else {

        state = "safe";
        color = "var(--safe)";
    }


    gaugeArc.style.stroke = color;


    assessmentPanel.classList.remove(
        "state-safe",
        "state-warn",
        "state-danger"
    );

    assessmentPanel.classList.add(
        `state-${state}`
    );


    gaugePercent.textContent =
        `${clamped.toFixed(2)}%`;

    gaugeVerdict.textContent =
        status === "Fraud"
            ? "Fraud flagged"
            : "Legitimate";


    return state;
}


// -----------------------------------------------------------
// Reset gauge
// -----------------------------------------------------------

function resetGauge() {

    gaugeArc.style.strokeDashoffset =
        GAUGE_CIRCUMFERENCE;

    gaugeArc.style.stroke =
        "var(--muted-2)";

    gaugePercent.textContent = "—";

    gaugeVerdict.textContent =
        "Awaiting input";

    assessmentPanel.classList.remove(
        "state-safe",
        "state-warn",
        "state-danger"
    );
}


// -----------------------------------------------------------
// Session ledger
// -----------------------------------------------------------

function addLedgerRow({
    cardId,
    percent,
    state,
    time
}) {

    if (ledgerEmpty) {
        ledgerEmpty.remove();
    }


    const row =
        document.createElement("li");

    row.className = "ledger__row";


    row.innerHTML = `
        <span class="ledger__badge ${state}"></span>

        <span class="ledger__id">
            ${escapeHtml(cardId)}
        </span>

        <span class="ledger__meta">
            ${percent.toFixed(1)}% · ${time}
        </span>
    `;


    ledgerList.prepend(row);


    // Keep only the latest 6 checks

    const rows =
        ledgerList.querySelectorAll(
            ".ledger__row"
        );

    if (rows.length > 6) {
        rows[rows.length - 1].remove();
    }


    sessionChecks += 1;


    ledgerCount.textContent =
        `${sessionChecks} check${sessionChecks === 1 ? "" : "s"}`;
}

async function loadTransactionHistory(cardId) {
    try {
        const response = await fetch(
            `${API_BASE_URL}/transactions/${encodeURIComponent(cardId)}`
        );

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const transactions = await response.json();

        // Clear existing history
        historyList.innerHTML = "";

        historyCount.textContent =
            `${transactions.length} transaction${transactions.length === 1 ? "" : "s"}`;

        // No transactions
        if (transactions.length === 0) {
            historyList.innerHTML = `
                <li class="ledger__empty">
                    No transactions found for this card.
                </li>
            `;
            return;
        }

        // Display transactions
        transactions.forEach((transaction) => {
            const row = document.createElement("li");

            const state =
                transaction.status === "Fraud"
                    ? "danger"
                    : "safe";

            row.className = "ledger__row";

            const dateTime = new Date(
                transaction.transaction_time
            );

            const date = dateTime.toLocaleDateString("en-IN", {
                day: "2-digit",
                month: "short",
                year: "numeric"
            });

            const time = dateTime.toLocaleTimeString("en-IN", {
                hour: "2-digit",
                minute: "2-digit"
            });
            row.innerHTML = `
                <span class="ledger__badge ${state}"></span>

                <span class="ledger__id">
                    ₹${Number(transaction.amount).toFixed(2)}
                </span>

                <span class="ledger__meta">
                    ${transaction.merchant_category}
                    · ${Number(transaction.fraud_probability).toFixed(1)}%
                    · ${time} ${time}
                </span>
            `;

            historyList.appendChild(row);
        });

    } catch (error) {
        console.error(
            "Failed to load transaction history:",
            error
        );

        historyList.innerHTML = `
            <li class="ledger__empty">
                Unable to load transaction history.
            </li>
        `;

        historyCount.textContent = "Error";
    }
}

function displayRiskAssessment(result) {

    riskAnalysis.hidden = false;

    riskFactorsList.innerHTML = "";

    const factors = result.risk_factors || [];

    factors.forEach((factor) => {

        const item = document.createElement("li");

        item.textContent = factor;

        riskFactorsList.appendChild(item);
    });

    riskRecommendationText.textContent =
        result.recommendation || "No recommendation available.";

    riskAnalysis.classList.remove(
        "risk-low",
        "risk-medium",
        "risk-high"
    );

    if (result.fraud_probability >= 80) {
        riskAnalysis.classList.add("risk-high");
    }
    else if (result.fraud_probability >= 50) {
        riskAnalysis.classList.add("risk-medium");
    }
    else {
        riskAnalysis.classList.add("risk-low");
    }
}

function displayModelWarnings(warnings) {

    const warningEl = document.getElementById("model-warning");

    if (!warningEl) return;

    if (warnings.length === 0) {
        warningEl.innerHTML = "";
        return;
    }

    warningEl.innerHTML = `
        <div class="model-warning">
            <div class="model-warning__title">
                ⚠ Model reliability warning
            </div>

            ${warnings.map(warning => `
                <div class="model-warning__item">
                    ${warning}
                </div>
            `).join("")}
        </div>
    `;
}

// -----------------------------------------------------------
// Prevent HTML injection in card ID
// -----------------------------------------------------------

function escapeHtml(str) {

    const div =
        document.createElement("div");

    div.textContent = str;

    return div.innerHTML;
}


// -----------------------------------------------------------
// Loading state
// -----------------------------------------------------------

function setLoading(isLoading) {

    submitBtn.disabled = isLoading;

    submitBtn.classList.toggle(
        "loading",
        isLoading
    );

    scanline.classList.toggle(
        "active",
        isLoading
    );
}


// -----------------------------------------------------------
// Form submission
// -----------------------------------------------------------

submitBtn.addEventListener("click", async () => {
    console.log("RUN BUTTON CLICKED");

    // Clear previous messages

    formError.textContent = "";

    modeNote.hidden = true;


    // -------------------------------------------------------
    // Read form values
    // -------------------------------------------------------

    const cardId =
        document.getElementById("card_id")
            .value
            .trim();

    const amount =
        parseFloat(
            document.getElementById("amount").value
        );

    const cardholderAge =
        parseInt(
            document.getElementById("cardholder_age").value,
            10
        );

    const merchantCategory =
        document.getElementById("merchant_category").value;

    const foreignTransaction =
        getPillValue("foreign_transaction");

    const locationMismatch =
        getPillValue("location_mismatch");

    const deviceTrustScore =
        parseFloat(trustSlider.value);

      console.log("FORM VALUES READ");


    // -------------------------------------------------------
    // Frontend validation
    // -------------------------------------------------------

    if (!cardId) {

        formError.textContent =
            "Please enter a card ID.";

        return;
    }


    if (Number.isNaN(amount) || amount <= 0) {

        formError.textContent =
            "Amount must be greater than zero.";

        return;
    }


    if (
        Number.isNaN(cardholderAge) ||
        cardholderAge < 18 ||
        cardholderAge > 120
    ) {

        formError.textContent =
            "Please enter a valid cardholder age.";

        return;
    }


    // -------------------------------------------------------
    // Create API payload
    // -------------------------------------------------------

    const payload = {

        card_id: cardId,

        amount: amount,

        cardholder_age: cardholderAge,

        merchant_category: merchantCategory,

        foreign_transaction: foreignTransaction,

        location_mismatch: locationMismatch,

        device_trust_score: deviceTrustScore

    };


    console.log(
        "Sending transaction:",
        payload
    );


    // -------------------------------------------------------
    // Start loading
    // -------------------------------------------------------

    setLoading(true);


    try {

        // ---------------------------------------------------
        // Send request to FastAPI
        // ---------------------------------------------------

        const response =
            await fetch(
                API_URL,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify(payload)
                }
            );


        // ---------------------------------------------------
        // Handle HTTP errors
        // ---------------------------------------------------

        if (!response.ok) {

            let errorMessage =
                `Server returned ${response.status}.`;

            try {

                const errorData =
                    await response.json();

                if (errorData.detail) {
                    errorMessage =
                        errorData.detail;
                }

            } catch {
                // Keep default error message
            }

            throw new Error(errorMessage);
        }


        // ---------------------------------------------------
        // Read prediction
        // ---------------------------------------------------

        const result =
            await response.json();

        const modelWarnings = result.model_warnings || [];

        console.log(
            "Prediction received:",
            result
        );

        displayRiskAssessment(result);

        displayModelWarnings(modelWarnings);

        await loadTransactionHistory(cardId);


        // Small delay for visual scanning effect

        await new Promise(
            resolve => setTimeout(resolve, 550)
        );


        // ---------------------------------------------------
        // Update gauge
        // ---------------------------------------------------

        const state =
            setGauge(
                result.fraud_probability,
                result.status
            );


        // ---------------------------------------------------
        // Update metadata
        // ---------------------------------------------------

        metaCardStatus.textContent =
            result.card_status || "—";


        metaVelocity.textContent =
            `${result.velocity_last_24h} transaction${
                result.velocity_last_24h === 1
                    ? ""
                    : "s"
            }`;


        const checkedAt =
            new Date(
                result.transaction_time ||
                Date.now()
            );


        metaTime.textContent =
            checkedAt.toLocaleTimeString(
                "en-IN",
                {
                    hour12: false
                }
            );


        // ---------------------------------------------------
        // Display backend message
        // ---------------------------------------------------

        if (result.message) {

            modeNote.hidden = false;

            modeNote.textContent =
                result.message;
        }


        // ---------------------------------------------------
        // Add to session log
        // ---------------------------------------------------

        addLedgerRow({

            cardId: cardId,

            percent:
                Number(
                    result.fraud_probability
                ),

            state: state,

            time:
                checkedAt.toLocaleTimeString(
                    "en-IN",
                    {
                        hour12: false,
                        hour: "2-digit",
                        minute: "2-digit"
                    }
                )
        });


    } catch (error) {

        console.error(
            "Fraud check failed:",
            error
        );


        // ---------------------------------------------------
        // Show real API error
        // ---------------------------------------------------

        formError.textContent =
            "Unable to connect to the fraud detection server. " +
            "Make sure FastAPI is running on port 8000.";


        modeNote.hidden = true;

    } finally {

        // ---------------------------------------------------
        // Stop loading
        // ---------------------------------------------------

        setLoading(false);
    }

});


// -----------------------------------------------------------
// Initial state
// -----------------------------------------------------------

resetGauge();