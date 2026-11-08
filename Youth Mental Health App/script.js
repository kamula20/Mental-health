
const assessmentForm = document.getElementById("assessmentForm");
const results = document.getElementById("results");
const resultMessage = document.getElementById("resultMessage");
const resultDetails = document.getElementById("resultDetails");
const resetButton = document.getElementById("resetButton");

assessmentForm.addEventListener("submit", function (event) {
    event.preventDefault();

    if (!assessmentForm.reportValidity()) {
        return;
    }

    const age = Number(document.getElementById("age").value);
    const screenTime = Number(document.getElementById("screenTime").value);
    const nightUse = Number(document.getElementById("nightUse").value);
    const passiveScrolling = Number(
        document.getElementById("passiveScrolling").value
    );
    const activeEngagement = Number(
        document.getElementById("activeEngagement").value
    );
    const platforms = Number(document.getElementById("platforms").value);
    const cyberbullying = document.getElementById("cyberbullying").value;
    const mood = document.getElementById("mood").value;

    if (
        age < 13 || age > 100 ||
        screenTime < 0 || screenTime > 24 ||
        platforms < 0 || platforms > 50
    ) {
        alert("Please check your answers and enter valid values.");
        return;
    }

    const observations = [];

    if (screenTime >= 5) {
        observations.push(
            "You reported five or more hours of daily social media use. " +
            "Consider whether your online activities leave enough time " +
            "for sleep, study, exercise, and offline relationships."
        );
    } else {
        observations.push(
            "Reflect on how social media fits into your daily routine " +
            "and whether it supports your personal goals."
        );
    }

    if (nightUse >= 3) {
        observations.push(
            "You reported frequent nighttime use. Consider setting a " +
            "bedtime screen limit and creating a relaxing routine."
        );
    }

    if (passiveScrolling >= 3) {
        observations.push(
            "You reported frequent passive scrolling. Consider taking " +
            "breaks and choosing activities that feel meaningful to you."
        );
    }

    if (activeEngagement >= 3) {
        observations.push(
            "You reported frequent active engagement. Reflect on whether " +
            "your online interactions feel supportive and positive."
        );
    }

    if (cyberbullying === "yes") {
        observations.push(
            "You indicated that you have experienced cyberbullying. " +
            "Consider saving evidence, blocking or reporting abusive " +
            "accounts, and talking with a trusted person."
        );
    } else if (cyberbullying === "unsure") {
        observations.push(
            "If an online interaction makes you feel unsafe or distressed, " +
            "consider discussing it with someone you trust."
        );
    }

    if (mood === "2" || mood === "3") {
        observations.push(
            "You reported experiencing low mood on several days. If this " +
            "is affecting your daily life, consider talking to a qualified " +
            "mental health professional or trusted support person."
        );
    }

    resultMessage.textContent =
        "Thank you for completing the assessment. Below is a summary " +
        "of your reported habits and some ideas for reflection.";

    resultDetails.replaceChildren();

    const heading = document.createElement("h3");
    heading.textContent = "Your responses";
    resultDetails.appendChild(heading);

    const summary = document.createElement("ul");

    const entries = [
        `Age: ${age}`,
        `Daily social media use: ${screenTime} hours`,
        `Regularly used platforms: ${platforms}`,
        `Nighttime use: ${getFrequencyLabel(nightUse)}`,
        `Passive scrolling: ${getFrequencyLabel(passiveScrolling)}`,
        `Active engagement: ${getFrequencyLabel(activeEngagement)}`
    ];

    entries.forEach(function (entry) {
        const item = document.createElement("li");
        item.textContent = entry;
        summary.appendChild(item);
    });

    resultDetails.appendChild(summary);

    const adviceHeading = document.createElement("h3");
    adviceHeading.textContent = "Ideas for reflection";
    resultDetails.appendChild(adviceHeading);

    const adviceList = document.createElement("ul");

    observations.forEach(function (observation) {
        const item = document.createElement("li");
        item.textContent = observation;
        adviceList.appendChild(item);
    });

    resultDetails.appendChild(adviceList);

    const disclaimer = document.createElement("p");
    disclaimer.textContent =
        "This is a rule-based educational summary, not a clinical " +
        "assessment or a validated mental health prediction. Social media " +
        "habits alone cannot determine a person's mental health.";
    resultDetails.appendChild(disclaimer);

    results.hidden = false;
    results.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
});

function getFrequencyLabel(value) {
    const labels = ["Never", "Rarely", "Sometimes", "Often", "Very often"];
    return labels[value] ?? "Not specified";
}

resetButton.addEventListener("click", function () {
    assessmentForm.reset();
    results.hidden = true;

    assessmentForm.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
});

