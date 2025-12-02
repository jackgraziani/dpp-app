//
//  addEquityView.swift
//  dpp-app-code
//
//  Created by Jack Graziani on 12/2/25.
//

import SwiftUI

struct addEquityView: View {
    @State private var ticker: String = ""
    @State private var numShares: String = "" //TODO: int
    @State private var loadedCompany: String = "Microsoft"
    
    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        HStack {
                            TextField("e.g., 'MSFT'", text: $ticker)
                            Spacer()
                        }
                        Button("Submit", action: {})
                    }
                    HStack {
                        Text("Ticker found:").foregroundColor(.gray)
                        Text(loadedCompany).foregroundColor(Color(red: 124/255, green: 215/255, blue: 124/255))
                    }
                } header: {Text("Equity Ticker")}
                Section {
                    HStack {
                        HStack {
                            TextField("e.g., 12", text: $numShares)
                        }
                        Button("Submit", action: {})
                    }
                } header: {Text("Number of Shares")}
            }
            .navigationTitle("Add Equity")
        }
    }
}

#Preview {
    addEquityView()
}
