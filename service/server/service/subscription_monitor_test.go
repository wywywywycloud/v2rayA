package service

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/v2rayA/v2rayA/core/touch"
	"github.com/v2rayA/v2rayA/db/configure"
)

func TestMonitorRecoveryCanBeCancelledWithoutBlockingSettings(t *testing.T) {
	old := resetSubscription(t)
	entered := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		close(entered)
		<-r.Context().Done()
	}))
	defer server.Close()
	old.Monitor, old.Address = true, server.URL
	if err := configure.SetSubscription(0, old); err != nil {
		t.Fatal(err)
	}
	configure.SetRunning(true)
	defer configure.SetRunning(false)
	target := activeMonitorTarget()
	target.client = server.Client()
	done := make(chan error, 1)
	go func() { done <- recoverMonitoredSubscription(context.Background(), target) }()
	select {
	case <-entered:
	case <-time.After(2 * time.Second):
		t.Fatal("recovery did not start")
	}
	if !ConfigurationMu.TryLock() {
		t.Fatal("background download blocks settings")
	}
	old.Monitor = false
	configure.SetSubscription(0, old)
	CancelSubscriptionRecovery()
	ConfigurationMu.Unlock()
	select {
	case err := <-done:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("expected cancellation: %v", err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("recovery did not cancel promptly")
	}
	if configure.GetSubscription(0).Monitor {
		t.Fatal("recovery overwrote disabled setting")
	}
}

func TestMonitorRequiresContinuousMinute(t *testing.T) {
	start := time.Unix(1000, 0)
	s := monitorState{}
	for _, elapsed := range []time.Duration{0, 10 * time.Second, 59 * time.Second} {
		if s.observe(start.Add(elapsed), false) {
			t.Fatal("recovery started before one minute")
		}
	}
	if !s.observe(start.Add(time.Minute), false) {
		t.Fatal("recovery did not start after one minute")
	}
	if s.observe(start.Add(65*time.Second), true) {
		t.Fatal("healthy result requested recovery")
	}
	if s.observe(start.Add(70*time.Second), false) {
		t.Fatal("intermittent failures accumulated")
	}
	if s.observe(start.Add(129*time.Second), false) {
		t.Fatal("new failure window too short")
	}
	if !s.observe(start.Add(130*time.Second), false) {
		t.Fatal("new continuous outage not detected")
	}
}

func TestMonitorRetriesImmediatelyThenBoundsLoad(t *testing.T) {
	s := monitorState{}
	for _, want := range []time.Duration{0, 5 * time.Second, 10 * time.Second, 20 * time.Second, 30 * time.Second, 30 * time.Second} {
		if got := s.retryDelay(); got != want {
			t.Fatalf("retry delay %s, want %s", got, want)
		}
	}
}

func TestMonitorTogglePersistsAndRespectsManualStop(t *testing.T) {
	old := resetSubscription(t)
	if old.Monitor {
		t.Fatal("monitor must default off")
	}
	if err := ModifySubscriptionRemark(touch.Subscription{ID: 1, Address: old.Address, Monitor: true}); err != nil {
		t.Fatal(err)
	}
	if !configure.GetSubscription(0).Monitor || !touch.GenerateTouch().Subscriptions[0].Monitor {
		t.Fatal("monitor setting not round-tripped")
	}
	if err := configure.SetRunning(false); err != nil {
		t.Fatal(err)
	}
	if activeMonitorTarget() != nil {
		t.Fatal("monitor would undo a manual stop")
	}
	if err := configure.SetRunning(true); err != nil {
		t.Fatal(err)
	}
	defer configure.SetRunning(false)
	if activeMonitorTarget() == nil {
		t.Fatal("enabled active subscription not monitored")
	}
	if err := configure.ClearConnects("proxy"); err != nil {
		t.Fatal(err)
	}
	if activeMonitorTarget() != nil {
		t.Fatal("unselected subscription monitored")
	}
}
