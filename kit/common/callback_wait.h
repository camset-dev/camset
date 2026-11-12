// callback_wait.h: the one wait a camera helper's main thread has on the SDK's callback thread, shared by camlink
// (kit/link) and the editor's camera helper (kit/probe). Commands run one at a time, so one wait is enough: the main
// thread arms it with what it waits for before the SDK call that leads to it, then waits; the SDK's thread ends it.
// An ending of another kind, or one that comes after the wait timed out, is ignored, so a late callback never ends
// the next command's wait, and nothing the callback thread touches lives on the main thread's stack. A late ending
// of the same kind (a download that timed out, finishing during the next one's wait) cannot be told apart by its kind;
// a wait armed with `expect` is ended well only by a text that carries it (the download's own temporary name), so the
// earlier download's file is never taken for this one's. Needs none of the SDK's headers; kit/common/guards_test.cpp
// checks it.
#pragma once

#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <string>

class CallbackWait {
public:
    enum class Ended { ok, failed, timedOut };

    // Before the SDK call: what the wait is for ("connect", "download", "upload", "disconnect", or "prop" with the
    // property's code, which its change notice names); "" disarms it. `expect`: text a good ending must carry (an
    // ending with no text at all is taken, having nothing to tell it by; a failure always is, naming nothing).
    void arm(const std::string& kind, uint32_t prop = 0, const std::string& expect = "") {
        std::lock_guard<std::mutex> l(m_);
        kind_ = kind;
        prop_ = prop;
        expect_ = expect;
        done_ = failed_ = false;
        detail_.clear();
    }

    // From the callback thread: the wait for `kind` ends, well or not, with the callback's text. Nothing ends while
    // the wait is disarmed, nor a good ending without the text the wait expects.
    void finish(const std::string& kind, bool ok, const std::string& detail = "") {
        std::lock_guard<std::mutex> l(m_);
        if (kind_.empty() || kind_ != kind) return;
        if (ok && !expect_.empty() && !detail.empty() && detail.find(expect_) == std::string::npos) return;
        end(ok, detail);
    }

    // From the callback thread: whatever wait is armed ends in failure (a disconnect, an error).
    void failAny(const std::string& detail) {
        std::lock_guard<std::mutex> l(m_);
        if (!kind_.empty()) end(false, detail);
    }

    // From the callback thread: a change notice for these property codes ends a "prop" wait armed for one of them.
    template <class Code>
    void changed(uint32_t count, const Code* codes) {
        std::lock_guard<std::mutex> l(m_);
        if (kind_ != "prop" || !codes) return;
        for (uint32_t k = 0; k < count; ++k)
            if (static_cast<uint32_t>(codes[k]) == prop_) return end(true, "");
    }

    // On the main thread: how the wait ended, within `timeout`; *detail gets the callback's text, or "<kind> timed
    // out". The wait is disarmed either way, so what comes later is ignored.
    Ended wait(std::chrono::milliseconds timeout, std::string* detail) {
        std::unique_lock<std::mutex> l(m_);
        const bool got = cv_.wait_for(l, timeout, [this] { return done_; });   // the predicate: spurious wakeups wait on
        const std::string kind = kind_;
        kind_.clear();
        if (!got) {
            if (detail) *detail = kind + " timed out";
            return Ended::timedOut;
        }
        if (detail) *detail = detail_;
        return failed_ ? Ended::failed : Ended::ok;
    }

    // wait(), true when the wait ended well.
    bool until(std::chrono::milliseconds timeout, std::string* detail) { return wait(timeout, detail) == Ended::ok; }

private:
    // With m_ held: the armed wait ends, once.
    void end(bool ok, const std::string& detail) {
        if (done_) return;
        done_ = true;
        failed_ = !ok;
        detail_ = detail;
        cv_.notify_all();
    }

    std::mutex m_;
    std::condition_variable cv_;
    std::string kind_, expect_;
    uint32_t prop_ = 0;
    bool done_ = false, failed_ = false;
    std::string detail_;
};
