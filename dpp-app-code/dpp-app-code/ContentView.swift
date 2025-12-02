//
//  ContentView.swift
//  dpp-app-code
//
//  Created by Jack Graziani on 12/1/25.
//

import SwiftUI

struct ContentView: View {
    @State private var showAddEquityScreen = false
    var body: some View {
        NavigationStack {
            List {
                Section {

                    Button("Add Equity  \(Image(systemName: "plus.circle"))", action: {showAddEquityScreen.toggle()})

                } header: {Text("Expand Portfolio")}
                Section {
                    
                } header :{Text("My Equities")}
            }.navigationTitle("My Portfolio")
        }
        .fullScreenCover(isPresented: $showAddEquityScreen, content: {
            NavigationStack {
                addEquityView()
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) {
                            Button("Cancel", action: {showAddEquityScreen.toggle()})
                        }
                        ToolbarItem {
                            Button("Done", action: {showAddEquityScreen.toggle()}).fontWeight(.medium)
                        }
                    }
            }
        })

    }
}

#Preview {
    ContentView()
}
