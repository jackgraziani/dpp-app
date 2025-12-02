//
//  dpp_widget_codeLiveActivity.swift
//  dpp-widget-code
//
//  Created by Jack Graziani on 12/1/25.
//

import ActivityKit
import WidgetKit
import SwiftUI

struct dpp_widget_codeAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        // Dynamic stateful properties about your activity go here!
        var emoji: String
    }

    // Fixed non-changing properties about your activity go here!
    var name: String
}

struct dpp_widget_codeLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: dpp_widget_codeAttributes.self) { context in
            // Lock screen/banner UI goes here
            VStack {
                Text("Hello \(context.state.emoji)")
            }
            .activityBackgroundTint(Color.cyan)
            .activitySystemActionForegroundColor(Color.black)

        } dynamicIsland: { context in
            DynamicIsland {
                // Expanded UI goes here.  Compose the expanded UI through
                // various regions, like leading/trailing/center/bottom
                DynamicIslandExpandedRegion(.leading) {
                    Text("Leading")
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text("Trailing")
                }
                DynamicIslandExpandedRegion(.bottom) {
                    Text("Bottom \(context.state.emoji)")
                    // more content
                }
            } compactLeading: {
                Text("L")
            } compactTrailing: {
                Text("T \(context.state.emoji)")
            } minimal: {
                Text(context.state.emoji)
            }
            .widgetURL(URL(string: "http://www.apple.com"))
            .keylineTint(Color.red)
        }
    }
}

extension dpp_widget_codeAttributes {
    fileprivate static var preview: dpp_widget_codeAttributes {
        dpp_widget_codeAttributes(name: "World")
    }
}

extension dpp_widget_codeAttributes.ContentState {
    fileprivate static var smiley: dpp_widget_codeAttributes.ContentState {
        dpp_widget_codeAttributes.ContentState(emoji: "😀")
     }
     
     fileprivate static var starEyes: dpp_widget_codeAttributes.ContentState {
         dpp_widget_codeAttributes.ContentState(emoji: "🤩")
     }
}

#Preview("Notification", as: .content, using: dpp_widget_codeAttributes.preview) {
   dpp_widget_codeLiveActivity()
} contentStates: {
    dpp_widget_codeAttributes.ContentState.smiley
    dpp_widget_codeAttributes.ContentState.starEyes
}
