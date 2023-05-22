var value;
var userName;
var base;
var peerIds;
var sentPerturbationMessages;
var id;
var aggregationResult = null;

function getRandomInt(max) {
  return Math.floor(Math.random() * max);
}

function modulo(a, b) {
  return ((a % b) + b) % b;
}

window.addEventListener("DOMContentLoaded", () => {
  // Open the WebSocket connection and register event handlers.
  var _websocket = new WebSocket("ws://137.165.191.239:8002/");

  _websocket.onopen = function () {
    console.log(`websocket connected`);
  };
  _websocket.onmessage = async function (evt) {
    console.log("Beginning message handler");
    await handleMessage(_websocket, evt);
    console.log("Done with message handler");
  };
  _websocket.onclose = function (evt) {
    if (evt.code == 3001) {
      console.log(`websocket closed.`);
      _websocket = null;
    } else {
      _websocket = null;
      console.log(`websocket connection error`);
    }
  };
  _websocket.onerror = function (evt) {
    if (_websocket.readyState == 1) {
      console.log(`websocket normal error: ` + evt.type);
    }
  };

  collectValue(_websocket);
});

async function collectValue(_websocket) {
  const form = document.querySelector("form");
  form.addEventListener("submit", (event) => {
    event.preventDefault();

    userName = document.getElementById("name").value;
    value = parseInt(document.getElementById("private-value").value);

    console.log(userName);
    console.log(value);

    $.post("/report-insecure", {
      id: id,
      data: {
        name: userName,
        value: value,
      },
    });

    _websocket.send(JSON.stringify({ type: "ready" }));

    document.getElementById("loading-div").setAttribute("style", "");
    document.getElementById("form").setAttribute("style", "display: none");

    window.setInterval(displayLoadingText, 2600);
  });
}

async function handleMessage(_websocket, message) {
  messageData = JSON.parse(message.data);
  console.log("Message received: ", messageData);

  messageType = messageData["type"];

  if (!messageType) {
    console.log("Message type not specified: ", messageData);
    return;
  }

  switch (messageType) {
    case "init_base_param":
      base = messageData["base"];
      break;
    case "your_id":
      id = messageData["id"];
      break;
    case "user_id_broadcast":
      // create and send perturbations
      perturbationMessages = await createPerturbations(messageData["user_ids"]);
      sentPerturbationMessages = perturbationMessages;

      // $.post("/report-my-perturbations", {
      //   id: id,
      //   data: {
      //     name: userName,
      //     perturbationMessages: perturbationMessages,
      //   },
      // });

      console.log("Perturbation messages: ", perturbationMessages);
      _websocket.send(
        JSON.stringify({
          type: "perturbations",
          perturbations: perturbationMessages,
        })
      );
      break;
    case "perturbations":
      maskedValue = await computeMaskedValue(messageData["perturbations"]);
      console.log("Masked value: ", maskedValue);

      $.post("/report-secure", {
        id: id,
        name: userName,
        value: maskedValue,
        perturbationMessages: sentPerturbationMessages,
      });

      _websocket.send(
        JSON.stringify({
          type: "value",
          value: maskedValue,
        })
      );
      break;
    case "aggregation_result":
      aggregationResult = messageData["aggregation_result"];
      window.location.href = `/result?agg=${aggregationResult}`;
      console.log("Aggregation result: ", aggregationResult);
      break;
    default:
      console.log("Unknown message type: " + messageType);
      return;
  }
}

async function createPerturbations(peerIds) {
  perturbations = {}; // peer -> perturbation

  for (peerId of peerIds) {
    if (peerId != id) {
      perturbations[peerId] = getRandomInt(base);
    }
  }

  return perturbations;
}

async function computeMaskedValue(peerPerturbations) {
  var maskedValue = 0;

  console.log("sentPerturbationMessages: ", sentPerturbationMessages);
  console.log("peer perturbs: ", Object.entries(peerPerturbations));

  for (const [peerId, recievedPerturbation] of Object.entries(
    peerPerturbations
  )) {
    if (peerId == id) {
      continue;
    }

    var s_uv = sentPerturbationMessages[peerId];
    console.log("s_uv: ", s_uv);

    var s_vu = recievedPerturbation;
    console.log("s_vu: ", s_vu);

    var p_uv = modulo(s_uv - s_vu, base);
    console.log("p_uv: ", p_uv);

    maskedValue += p_uv;
  }

  return modulo(maskedValue + value, base);
}

// Logic for funny loading text, taken from here: https://stackoverflow.com/questions/6398526/javascript-jquery-or-something-to-change-text-every-some-seconds
var text = [
  "Hacking the mainframe...",
  "Building several peer-to-peer networks...",
  "Asking Jae for help...",
  "Leveraging tree-like hierarchies...",
  "Optimizing yield and harvest...",
  "Increasing scalability, availability, and reliability...",
  "Figuring out if this could be a blockchain...",
  "Checking my email using Porcupine...",
  "Running a botnet...",
];
var counter = 0;
function displayLoadingText() {
  console.log("here");
  var elem = document.getElementById("loading-text");
  elem.innerHTML = text[counter];
  counter++;
  if (counter >= text.length) {
    counter = 0;
  }
}
