// English / Hindi for the shopkeeper's app.
//
// How it works: every visible string goes through t("English text"). In
// Hindi mode it's looked up in HI below; anything missing falls back to the
// English, so a forgotten string never breaks a screen. {name}-style
// placeholders are filled in after translation, so word order can differ.
//
// The chosen language is saved in the browser (localStorage). Changing it
// re-renders the whole app (see main.jsx).
//
// The Results screen stays in English on purpose: it's the owner's
// experiment view, not part of the shopkeeper's day.

const HI = {
  // shell
  Today: "आज",
  Calls: "कॉल",
  Customers: "ग्राहक",
  Activity: "गतिविधि",
  Results: "नतीजे",
  Settings: "सेटिंग्स",
  "Your shop": "आपकी दुकान",
  "Concept prototype, all simulated": "प्रोटोटाइप, सब सिम्युलेटेड",
  "Demo shop with generated data": "डेमो दुकान, बनाया गया डेटा",
  "Can’t reach the app server.": "ऐप सर्वर से संपर्क नहीं हो पा रहा।",

  // Today
  "No one owes you anything right now.": "अभी किसी पर कोई उधार बाकी नहीं है।",
  "{amount} pending with {count} customers": "{count} ग्राहकों पर {amount} बाकी",
  "{amount} pending with 1 customer": "1 ग्राहक पर {amount} बाकी",
  "Finish setting up": "सेटअप पूरा करें",
  "Add your shop’s UPI ID so customers can pay from their message": "अपनी दुकान का UPI ID जोड़ें ताकि ग्राहक मैसेज से भुगतान कर सकें",
  "Approve the weekly reminder message": "हफ़्ते का याद-संदेश मंज़ूर करें",
  "Customer’s phone number": "ग्राहक का फ़ोन नंबर",
  "Existing customer": "पुराने ग्राहक",
  ", already owes": ", पहले से बाकी",
  ", nothing pending": ", कुछ बाकी नहीं",
  "Opted out of messages.": "मैसेज बंद करवाए हैं।",
  "New customer. Name (optional)": "नया ग्राहक। नाम (ज़रूरी नहीं)",
  Bill: "बिल",
  "Paid now": "अभी दिए",
  "goes on credit": "उधार में जाएगा",
  "Fully paid. Nothing to add to credit.": "पूरा भुगतान हो गया। उधार में कुछ नहीं।",
  "Save {amount} on credit": "{amount} उधार में लिखें",
  "Save on credit": "उधार में लिखें",
  "Saving…": "सेव हो रहा है…",
  "Add what they bought (optional)": "क्या खरीदा, लिखें (ज़रूरी नहीं)",
  "What they bought (optional, helps if there’s a disagreement later)": "क्या खरीदा (ज़रूरी नहीं, बाद में विवाद हो तो काम आता है)",
  "Add another item": "और सामान जोड़ें",
  Item: "सामान",
  Qty: "मात्रा",
  "Saved {amount} for {who}. They now owe {total}.": "{who} के लिए {amount} लिखा गया। अब कुल बाकी {total}।",
  "Payment message sent.": "भुगतान का मैसेज भेज दिया।",
  "It’s quiet hours, so the payment message goes at {time}.": "रात का समय है, इसलिए मैसेज {time} बजे जाएगा।",
  "No message sent: this customer opted out.": "मैसेज नहीं भेजा: ग्राहक ने मैसेज बंद करवाए हैं।",
  "Payments to check": "जाँचने वाले भुगतान",
  "{n} waiting": "{n} बाकी",
  "Nothing to check. When a UPI payment clearly belongs to a customer, it’s marked paid automatically.":
    "जाँचने को कुछ नहीं। जब UPI भुगतान साफ़ तौर पर किसी ग्राहक का हो, तो अपने आप जमा हो जाता है।",
  from: "से",
  "Their note: “{note}”.": "उनका नोट: “{note}”।",
  "No note.": "कोई नोट नहीं।",
  "Yes, it’s {name}": "हाँ, ये {name} हैं",
  "Someone else": "कोई और",
  "It’s a regular sale": "ये सामान्य बिक्री है",
  "Who paid?": "किसने भुगतान किया?",
  "Mark paid": "जमा करें",
  "Call {n} customers": "{n} ग्राहकों को कॉल करें",
  "Call 1 customer": "1 ग्राहक को कॉल करें",
  "Open call list": "कॉल लिस्ट खोलें",
  Customer: "ग्राहक",

  "This takes them over their credit limit of {limit} (they would owe {total}). You can still save it.":
    "इससे उनकी उधार सीमा {limit} पार हो जाएगी (कुल बाकी {total})। फिर भी सेव कर सकते हैं।",
  "Credit limit: {limit}": "उधार सीमा: {limit}",
  "Credit limit: {limit} (shop default)": "उधार सीमा: {limit} (दुकान की सामान्य)",
  "No credit limit": "कोई उधार सीमा नहीं",
  Change: "बदलें",
  Save: "सेव करें",
  "Limit ₹ (empty = shop default)": "सीमा ₹ (खाली = दुकान की सामान्य)",
  "Credit limit": "उधार सीमा",
  "A warning when a sale would take a customer over this amount. It never blocks the sale.":
    "जब कोई बिक्री ग्राहक को इस रकम से ऊपर ले जाए, तो चेतावनी। बिक्री कभी नहीं रुकती।",
  "Default limit for every customer, ₹ (empty = no limit)": "हर ग्राहक के लिए सामान्य सीमा, ₹ (खाली = कोई सीमा नहीं)",
  "You can set a different limit for one customer on their page.": "किसी एक ग्राहक की अलग सीमा उनके पेज पर रख सकते हैं।",
  "Suggest a part payment in reminders": "याद-संदेश में थोड़ा भुगतान सुझाएँ",
  "Extra reminder on the 1st of the month": "महीने की 1 तारीख को एक और याद-संदेश",

  // Calls
  "Customers whose dues are old enough that a call works better than another message.":
    "जिनका उधार इतना पुराना है कि अब मैसेज से बेहतर कॉल करना है।",
  "To call": "कॉल करने हैं",
  "No one to call right now. Customers appear here when their oldest bill passes the limit in Settings (30 days by default), and their automatic reminders stop.":
    "अभी किसी को कॉल नहीं करना। जब किसी का सबसे पुराना बिल सेटिंग्स की सीमा (आम तौर पर 30 दिन) पार करता है, तो वे यहाँ आते हैं और अपने आप याद-संदेश बंद हो जाते हैं।",
  "Promised to pay": "भुगतान का वादा",
  "By {date}. Reminders are paused until then.": "{date} तक। तब तक याद-संदेश रुके हैं।",
  Disputed: "विवाद",
  "No messages go to these customers until you sort it out.": "जब तक आप मामला नहीं सुलझाते, इन्हें कोई मैसेज नहीं जाएगा।",
  "Call {phone}": "कॉल करें {phone}",
  "After the call:": "कॉल के बाद:",
  "Promised a date": "तारीख का वादा किया",
  "Write off": "बट्टे खाते में डालें",
  "When did they say they’ll pay?": "कब तक देने को कहा?",
  Tomorrow: "कल",
  "In 3 days": "3 दिन में",
  "In a week": "एक हफ़्ते में",
  "Note (optional), e.g. after salary": "नोट (ज़रूरी नहीं), जैसे तनख्वाह के बाद",
  "Save promise": "वादा सेव करें",
  Back: "वापस",
  "What do they disagree with? (optional)": "किस बात पर असहमति है? (ज़रूरी नहीं)",
  "All messages to them stop until you mark it resolved.": "सुलझने तक इन्हें सभी मैसेज बंद रहेंगे।",
  "Mark as disputed": "विवाद में डालें",
  "Write off {amount}": "{amount} बट्टे खाते में डालें",
  "Sorted out, resume": "सुलझ गया, फिर शुरू करें",
  "Oldest bill {n} days old": "सबसे पुराना बिल {n} दिन का",
  "Last reminder {when}.": "आखिरी याद-संदेश {when}।",
  "No reminder sent yet.": "अभी कोई याद-संदेश नहीं गया।",
  "Oldest bill is {n} days old": "सबसे पुराना बिल {n} दिन का है",
  "Owes {amount}, oldest bill {n} days old": "{amount} बाकी, सबसे पुराना बिल {n} दिन का",
  "Promised {date}, didn't pay": "{date} का वादा किया था, पर भुगतान नहीं हुआ",
  "Kept their promise for {date}.": "{date} का वादा निभाया।",
  "Reminders pause until {date}. That morning they get one gentle reminder.": "{date} तक याद-संदेश रुकेंगे। उस सुबह एक हल्का याद-संदेश जाएगा।",
  "Write off {amount}? Their bills are closed as unpaid and they won’t get any more reminders. The record stays in their history.":
    "{amount} बट्टे खाते में डालें? उनके बिल बिना भुगतान बंद हो जाएँगे और याद-संदेश नहीं जाएँगे। रिकॉर्ड उनके हिसाब में रहेगा।",
  "Promised date": "वादे की तारीख",

  // Customers
  "Biggest balance first.": "सबसे ज़्यादा बाकी वाले पहले।",
  "Search by name or phone": "नाम या फ़ोन से खोजें",
  "Loading…": "लोड हो रहा है…",
  Settled: "हिसाब साफ़",
  "All customers": "सभी ग्राहक",
  "Owes you": "आपका बाकी",
  "Record payment": "भुगतान दर्ज करें",
  "Amount ₹": "रकम ₹",
  History: "हिसाब-किताब",
  "Stop messages": "मैसेज बंद करें",
  "Resume messages": "मैसेज फिर शुरू करें",
  "Paid at the counter": "दुकान पर दिए",
  "Paid by UPI": "UPI से दिए",
  "They replied": "ग्राहक का जवाब",

  // Activity
  "Messages and UPI payments, grouped by customer. All simulated.": "मैसेज और UPI भुगतान, ग्राहक के हिसाब से। सब सिम्युलेटेड।",
  All: "सभी",
  Messages: "मैसेज",
  "UPI payments": "UPI भुगतान",
  "Demo time": "डेमो समय",
  "+1 day": "+1 दिन",
  "+1 week": "+1 हफ़्ता",
  "Back to real time": "असली समय पर लौटें",
  "Not linked to a customer": "किसी ग्राहक से नहीं जुड़ा",

  // Settings
  "Set these once. You can change them any time.": "एक बार सेट करें। कभी भी बदल सकते हैं।",
  Language: "भाषा",
  "App language": "ऐप की भाषा",
  "Changing the message language switches the standard reminder wording and needs approval again.":
    "मैसेज की भाषा बदलने पर सामान्य याद-संदेश भी बदल जाता है और फिर से मंज़ूरी चाहिए।",
  "Language of messages to customers": "ग्राहकों को जाने वाले मैसेज की भाषा",
  "Shop name, as customers see it": "दुकान का नाम, जैसा ग्राहक देखेंगे",
  "Shop’s UPI ID, the one behind your QR code": "दुकान का UPI ID, जो आपके QR कोड में है",
  "Weekly reminder": "हफ़्ते का याद-संदेश",
  Day: "दिन",
  Time: "समय",
  Message: "मैसेज",
  "How the customer sees it": "ग्राहक को ऐसा दिखेगा",
  "Approve this reminder": "यह याद-संदेश मंज़ूर करें",
  "When to suggest a call": "कॉल कब सुझाएँ",
  "Being polite": "शिष्टता के नियम",
  Experiment: "प्रयोग",
  "Save changes": "बदलाव सेव करें",
  "Changes saved.": "बदलाव सेव हो गए।",
};

let current = (typeof localStorage !== "undefined" && localStorage.getItem("lang")) || "en";

export function getLang() {
  return current;
}

export function setLang(lang) {
  current = lang === "hi" ? "hi" : "en";
  localStorage.setItem("lang", current);
  document.documentElement.lang = current;
  window.dispatchEvent(new Event("lang-change"));
}

export function t(text, vars) {
  let out = current === "hi" ? HI[text] ?? text : text;
  if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined ? vars[k] : m));
  return out;
}

// Like t(), but placeholders can be React elements (e.g. a red amount), so a
// translated sentence can keep styled parts in whatever order the language needs.
export function tx(text, vars) {
  const template = current === "hi" ? HI[text] ?? text : text;
  return template.split(/(\{\w+\})/).map((part, i) => {
    const m = part.match(/^\{(\w+)\}$/);
    return m && vars[m[1]] !== undefined ? <span key={i}>{vars[m[1]]}</span> : part;
  });
}

if (typeof document !== "undefined") document.documentElement.lang = current;
