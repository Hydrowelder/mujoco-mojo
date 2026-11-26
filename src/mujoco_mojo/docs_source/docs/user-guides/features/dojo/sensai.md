# SensAI Chat

!!! abstract

    The **SensAI chat** is [SensAI](../sensai.md) in the Dojo. Ask it about your job (_which trial took the longest?_), what your trials were sampled from (_what is the wind speed drawn from?_), tell it to change your plot (_plot the x position of box2 and make it red_) or to compare trials in [versus mode](mosaic.md#versus-mode) (_compare the trials where wind speed was 2 or more standard deviations out_), ask what a trial recorded, ask how to do something in Mojo (_how do I add a requirement?_), or ask what a setting does (_how do I start the Dojo in fullscreen?_). It answers in plain language, using the same data the Dojo shows you.

    [Set SensAI up](../sensai.md#setting-it-up) first, and a sparkle button appears at the bottom right of every Dojo page. SensAI can make mistakes, so please verify its answers and any changes it makes before relying on them.

---

## The chat window

Press the sparkle button to open the chat. Type and press ++enter++ (++shift+enter++ for a new line). While it works, the window shows what it is doing, and the reply follows.

<figure markdown="span">
    ![SensAI chat](../../../assets/user-guides/light-sensai-chat.jpg#only-light){ width="60%" height="auto" }
    ![SensAI chat](../../../assets/user-guides/dark-sensai-chat.jpg#only-dark){ width="60%" height="auto" }
    <figcaption>The <b>SensAI</b> window, pinned open, with an answer and the tool calls that produced it.</figcaption>
</figure>

- **Tabs:** each tab is its own conversation, titled with the start of its first message. Add one with **+**, rename it by double-clicking its title, and close it with its **x**, which is how you clear a chat. Up to eight can be open, and your browser remembers them.
- **One at a time:** requests run in the order you sent them. While one chat waits, you can write in another, and each answer lands in the tab that asked, with a mark if you were looking elsewhere. Two plot edits running together would overwrite each other, which is why.
- **Pin:** keeps the window open when you click elsewhere or press ++esc++. Unpinned, a click outside closes it.
- **Tool calls:** every reply lists the calls behind it, such as what it asked the job report for or which signals it added, live while it works and as a closed _N tool calls_ line afterward. A call the server turned away is shown with its reason.
- **Copy and the model:** each message has a copy button, and hovering the row above a reply shows which of your models wrote it, which tells you when a fallback answered.
- **Long messages:** the latest stays open and older ones fold to a preview you can click open.
- **Context and Compact:** under the box, how much of the model's context window the chat takes up, and **Compact**, which summarizes it so far so SensAI goes on from the summary. SensAI also does that by itself once the chat grows long (see [long conversations](../sensai.md#long-conversations)).
- **Chat history:** the [export menu](mosaic.md#export-options) can download the conversation.

What the chat can do depends on which of SensAI's [features](../sensai.md#choosing-what-it-can-do) are on. Ask for one that is off and it tells you so.

---

!!! tip "Getting a good answer"

    Ask for one thing at a time, and name signals and trials the way the Dojo shows them, or say what a signal measures: SensAI also searches the [descriptions](../mojo-dataframe.md#metadata-units-tags-and-labels) of the signals, so "the box's angular velocity" can find `Bodies/box1/xvelr:y`. The built-in signals describe themselves, and you can describe your own. A small model can pick the wrong edit; the server refuses an invalid one and the model gets a few tries, and if it still cannot, the plot stays as it was and you are told why. If a chat stops with an error about the number of requests, raise [`sensai.max_requests`](../sensai.md#limits) or split the ask.

---

!!! success

    SensAI is a shortcut to everything else in the Dojo, not a replacement for it. To do what it does by hand, see the [Mosaic](mosaic.md) and [Monitor](monitor.md) guides.
