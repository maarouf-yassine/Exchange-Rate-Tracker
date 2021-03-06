package com.maarouf.currencyexchange.api

import com.maarouf.currencyexchange.api.model.*
import retrofit2.Call
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST


class retrofit {

}
object ExchangeService {
    private const val API_URL: String = "http://10.0.2.2:5000"
    fun exchangeApi():Exchange {
        val retrofit: Retrofit = Retrofit.Builder()
            .baseUrl(API_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        // Create an instance of our Exchange API interface.
        return retrofit.create(Exchange::class.java)
    }
    interface Exchange {
        @GET("/exchangeRate")
        fun getExchangeRates(): Call<ExchangeRates>

        @POST("/transaction")
        fun addTransaction(@Body transaction: Transaction, @Header("Authorization") authorization : String?): Call<Any>

        @POST("/user")
        fun addUser(@Body user : User): Call<User>

        @POST("/authentication")
        fun authenticate(@Body user : User): Call<Token>

        @GET("/transaction")
        fun getTransactions(@Header("Authorization") authorization: String): Call<List<Transaction>>

        @GET("/graph")
        fun getGraphDataPoints(): Call<GraphDataPoints>

        @GET("/insights")
        fun getInsights(): Call<InsightsData>

        @GET("/listings")
        fun getListings(): Call<List<ListingsData>>

        @POST("/listing")
        fun addListing(@Body listingsData: ListingsData, @Header("Authorization") authorization : String?): Call<Any>

    }
}